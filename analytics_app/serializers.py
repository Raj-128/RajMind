from rest_framework import serializers
from django.db.models import Avg, Count
from .models import SearchAnalytics


class SearchAnalyticsSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = SearchAnalytics
        fields = ['id', 'query', 'user_email', 'response_time', 'sources_count', 'created_at']