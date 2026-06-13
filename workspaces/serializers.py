from rest_framework import serializers
from .models import Workspace, WorkspaceMember
from django.utils.text import slugify
import uuid


class WorkspaceSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ['id', 'name', 'slug', 'owner_email', 'member_count', 'created_at']
        read_only_fields = ['slug', 'owner_email', 'member_count', 'created_at']

    def get_member_count(self, obj):
        return obj.members.count()

    def create(self, validated_data):
        base_slug = slugify(validated_data['name'])
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
        validated_data['slug'] = slug
        validated_data['owner'] = self.context['request'].user
        workspace = Workspace.objects.create(**validated_data)
        # Auto-add owner as member
        WorkspaceMember.objects.create(workspace=workspace, user=workspace.owner, role='owner')
        return workspace


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ['id', 'user_email', 'user_full_name', 'role', 'joined_at']
        read_only_fields = ['joined_at']


class AddMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=['admin', 'member', 'viewer'])