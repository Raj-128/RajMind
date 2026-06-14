from rest_framework import serializers
from .models import Document, DocumentChunk


class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True)
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'file', 'file_type', 'status',
            'uploaded_by_email', 'workspace_name', 'created_at'
        ]
        read_only_fields = ['status', 'file_type', 'uploaded_by_email', 'workspace_name', 'created_at']

    def validate_file(self, value):
        allowed_extensions = ['pdf', 'docx', 'txt']
        ext = value.name.split('.')[-1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError('Only PDF, DOCX, and TXT files are allowed.')
        if value.size > 10 * 1024 * 1024:  # 10MB limit
            raise serializers.ValidationError('File size must not exceed 10MB.')
        return value

    def create(self, validated_data):
        file = validated_data['file']
        ext = file.name.split('.')[-1].lower()
        validated_data['file_type'] = ext
        validated_data['uploaded_by'] = self.context['request'].user
        validated_data['workspace'] = self.context['workspace']
        return Document.objects.create(**validated_data)


class DocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunk
        fields = ['id', 'chunk_index', 'content', 'created_at']