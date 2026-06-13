from django.contrib import admin
from .models import Workspace, WorkspaceMember

admin.site.register(Workspace)
admin.site.register(WorkspaceMember)