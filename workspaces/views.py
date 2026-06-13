from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Workspace, WorkspaceMember
from .serializers import WorkspaceSerializer, WorkspaceMemberSerializer, AddMemberSerializer
from accounts.models import User


class WorkspaceListCreateView(generics.ListCreateAPIView):
    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Workspace.objects.filter(members__user=self.request.user)


class WorkspaceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Workspace.objects.filter(members__user=self.request.user)


class WorkspaceMemberListView(generics.ListAPIView):
    serializer_class = WorkspaceMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        workspace = get_object_or_404(Workspace, id=self.kwargs['workspace_id'], members__user=self.request.user)
        return workspace.members.all()


class AddMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Only owner or admin can add members
        requester = WorkspaceMember.objects.filter(workspace=workspace, user=request.user, role__in=['owner', 'admin']).first()
        if not requester:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = AddMemberSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(email=serializer.validated_data['email'])
            except User.DoesNotExist:
                return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

            member, created = WorkspaceMember.objects.get_or_create(
                workspace=workspace, user=user,
                defaults={'role': serializer.validated_data['role']}
            )
            if not created:
                return Response({'error': 'User already a member.'}, status=status.HTTP_400_BAD_REQUEST)

            return Response(WorkspaceMemberSerializer(member).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RemoveMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, workspace_id, user_id):
        workspace = get_object_or_404(Workspace, id=workspace_id)

        requester = WorkspaceMember.objects.filter(workspace=workspace, user=request.user, role__in=['owner', 'admin']).first()
        if not requester:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        member = get_object_or_404(WorkspaceMember, workspace=workspace, user__id=user_id)
        if member.role == 'owner':
            return Response({'error': 'Cannot remove owner.'}, status=status.HTTP_400_BAD_REQUEST)

        member.delete()
        return Response({'message': 'Member removed.'}, status=status.HTTP_200_OK)