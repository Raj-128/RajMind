from django.db import models
from django.conf import settings
from workspaces.models import Workspace


class SearchAnalytics(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='search_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='search_logs')
    query = models.TextField()
    response_time = models.FloatField(help_text="Time in seconds")
    sources_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.query[:50]} - {self.workspace.name}"