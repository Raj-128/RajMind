from django.urls import path
from . import views

urlpatterns = [
    path('', views.WorkspaceListCreateView.as_view(), name='workspace-list-create'),
    path('<int:pk>/', views.WorkspaceDetailView.as_view(), name='workspace-detail'),
    path('<int:workspace_id>/members/', views.WorkspaceMemberListView.as_view(), name='workspace-members'),
    path('<int:workspace_id>/members/add/', views.AddMemberView.as_view(), name='add-member'),
    path('<int:workspace_id>/members/<int:user_id>/remove/', views.RemoveMemberView.as_view(), name='remove-member'),
]