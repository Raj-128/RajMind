from rest_framework import serializers
from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'sources', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'user_email', 'messages', 'created_at']
        read_only_fields = ['user_email', 'created_at']


class ConversationListSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'user_email', 'created_at']


class AskQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)