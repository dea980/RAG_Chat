from django.urls import path
from . import views

urlpatterns = [
    path("chat/", views.ChatAPIView.as_view(), name='chat-create'),
    path("chat-user/", views.ChatUserAPIView.as_view(), name='chat-user'),
    path("chat-rag/", views.ChatRagAPIView.as_view(), name='chat-rag'),
    path("update-activity/", views.UpdateActivityAPIView.as_view(), name='update-activity'),
    path("search-logs/", views.SearchLogAPIView.as_view(), name='search-logs'),
    
    # Metadata endpoints
    path("metadata/", views.MetaDataAPIView.as_view(), name='metadata-list'),
    path("metadata/<str:key>/", views.MetaDataAPIView.as_view(), name='metadata-detail'),
]