from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    ConversationListSerializer,
    AskQuestionSerializer,
    MessageSerializer
)
import logging
import time
from google.genai import errors as genai_errors
from analytics_app.models import SearchAnalytics
from .ai_engine import generate_answer
from workspaces.models import Workspace, WorkspaceMember

logger = logging.getLogger(__name__)


class ConversationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ConversationListSerializer
        return ConversationSerializer

    def get_queryset(self):
        workspace_id = self.kwargs['workspace_id']
        return Conversation.objects.filter(
            workspace_id=workspace_id,
            user=self.request.user
        ).order_by('-updated_at')

    def perform_create(self, serializer):
        workspace = get_object_or_404(Workspace, id=self.kwargs['workspace_id'], members__user=self.request.user)
        serializer.save(user=self.request.user, workspace=workspace)


class ConversationDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user, workspace_id=self.kwargs['workspace_id'])


class AskQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        # Check workspace membership
        workspace = get_object_or_404(Workspace, id=workspace_id)
        is_member = WorkspaceMember.objects.filter(
            workspace=workspace,
            user=request.user
        ).exists()

        if not is_member:
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = AskQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        question = serializer.validated_data['question']
        conversation_id = serializer.validated_data.get('conversation_id')

        # Get or create conversation
        if conversation_id:
            conversation = get_object_or_404(
                Conversation,
                id=conversation_id,
                user=request.user,
                workspace=workspace
            )
        else:
            conversation = Conversation.objects.create(
                workspace=workspace,
                user=request.user,
                title=question[:50]
            )

        # Get conversation history
        history = list(conversation.messages.values('role', 'content'))

        # Save user message
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=question
        )

        # Generate AI answer
        start_time = time.time()
        try:
            result = generate_answer(workspace_id, question, history)
        except genai_errors.APIError as e:
            logger.exception("Gemini call failed while answering")
            if e.code == 429:
                message = "The AI is at its free usage limit for this minute. Please try again in about a minute."
            else:
                message = "The AI service is unavailable right now. Please try again shortly."
            return Response({'error': message}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            # e.g. the Groq fallback also failed; answer with a clear message, not a bare 500.
            logger.exception("Answer generation failed")
            return Response({'error': "The AI service is unavailable right now. Please try again shortly."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        elapsed_time = time.time() - start_time

        # Save assistant message
        assistant_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=result['answer'],
            sources=result['sources']
        )
        conversation.save(update_fields=['updated_at'])  # bump to top of the history list

        # Log analytics
        SearchAnalytics.objects.create(
            workspace=workspace,
            user=request.user,
            query=question,
            response_time=elapsed_time,
            sources_count=len(result['sources'])
        )

        return Response({
            'conversation_id': conversation.id,
            'question': question,
            'answer': result['answer'],
            'sources': result['sources'],
            'message_id': assistant_message.id
        }, status=status.HTTP_200_OK)