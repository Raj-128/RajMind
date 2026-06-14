from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta
from .models import SearchAnalytics
from .serializers import SearchAnalyticsSerializer
from workspaces.models import Workspace, WorkspaceMember
from documents.models import Document
from chat.models import Conversation


class AnalyticsDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        workspace = get_object_or_404(Workspace, id=workspace_id)

        is_member = WorkspaceMember.objects.filter(workspace=workspace, user=request.user).exists()
        if not is_member:
            return Response({'error': 'Access denied.'}, status=403)

        # Overview stats
        total_documents = Document.objects.filter(workspace=workspace).count()
        total_conversations = Conversation.objects.filter(workspace=workspace).count()
        total_searches = SearchAnalytics.objects.filter(workspace=workspace).count()

        avg_response_time = SearchAnalytics.objects.filter(
            workspace=workspace
        ).aggregate(avg=Avg('response_time'))['avg'] or 0

        # Last 7 days activity
        last_week = timezone.now() - timedelta(days=7)
        recent_searches = SearchAnalytics.objects.filter(
            workspace=workspace,
            created_at__gte=last_week
        ).count()

        # Most active users
        top_users = SearchAnalytics.objects.filter(
            workspace=workspace
        ).values('user__email').annotate(
            search_count=Count('id')
        ).order_by('-search_count')[:5]

        # Recent searches
        recent_queries = SearchAnalytics.objects.filter(
            workspace=workspace
        ).order_by('-created_at')[:10]

        return Response({
            'overview': {
                'total_documents': total_documents,
                'total_conversations': total_conversations,
                'total_searches': total_searches,
                'avg_response_time': round(avg_response_time, 2),
                'searches_last_7_days': recent_searches,
            },
            'top_users': list(top_users),
            'recent_searches': SearchAnalyticsSerializer(recent_queries, many=True).data
        })


class DocumentUsageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        workspace = get_object_or_404(Workspace, id=workspace_id)

        is_member = WorkspaceMember.objects.filter(workspace=workspace, user=request.user).exists()
        if not is_member:
            return Response({'error': 'Access denied.'}, status=403)

        documents = Document.objects.filter(workspace=workspace).values(
            'id', 'title', 'status', 'file_type', 'created_at'
        )

        return Response({'documents': list(documents)})