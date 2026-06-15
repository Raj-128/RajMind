from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Document
from .serializers import DocumentSerializer
from workspaces.models import Workspace, WorkspaceMember
from rag.tasks import process_document_task

def get_workspace_or_403(workspace_id, user):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    is_member = WorkspaceMember.objects.filter(workspace=workspace, user=user).exists()
    if not is_member:
        return None, workspace
    return workspace, None


class DocumentListCreateView(generics.ListCreateAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        workspace_id = self.kwargs['workspace_id']
        workspace, _ = get_workspace_or_403(workspace_id, self.request.user)
        if not workspace:
            return Document.objects.none()
        return Document.objects.filter(workspace=workspace).order_by('-created_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        workspace_id = self.kwargs['workspace_id']
        workspace, _ = get_workspace_or_403(workspace_id, self.request.user)
        context['workspace'] = workspace
        return context

    def create(self, request, *args, **kwargs):
        workspace_id = self.kwargs['workspace_id']
        workspace, error = get_workspace_or_403(workspace_id, request.user)
        if not workspace:
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        process_document_task.delay(document.id)

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)
class DocumentDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        workspace_id = self.kwargs['workspace_id']
        workspace, _ = get_workspace_or_403(workspace_id, self.request.user)
        if not workspace:
            return Document.objects.none()
        return Document.objects.filter(workspace=workspace)