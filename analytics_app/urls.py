from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path('documents/', views.DocumentUsageView.as_view(), name='document-usage'),
]