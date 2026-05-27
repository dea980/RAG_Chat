from django.urls import path
from . import views
from .health import LivenessView, ReadinessView
from .ingest_views import IngestPreviewAPIView, IngestUploadAPIView
from .token_views import TokenEstimateAPIView

urlpatterns = [
    path("chat/", views.ChatAPIView.as_view(), name='chat-create'),
    path("chat-user/", views.ChatUserAPIView.as_view(), name='chat-user'),
    path("chat-rag/", views.ChatRagAPIView.as_view(), name='chat-rag'),
    path("update-activity/", views.UpdateActivityAPIView.as_view(), name='update-activity'),
    path("providers/", views.ProviderConfigAPIView.as_view(), name='provider-config'),
    path("search-logs/", views.SearchLogAPIView.as_view(), name='search-logs'),

    # Metadata endpoints
    path("metadata/", views.MetaDataAPIView.as_view(), name='metadata-list'),
    path("metadata/<str:key>/", views.MetaDataAPIView.as_view(), name='metadata-detail'),

    # Ingest preview (chunk_lab 페이지 용 — 저장/임베딩 X)
    path("ingest/preview/", IngestPreviewAPIView.as_view(), name='ingest-preview'),
    path("ingest/upload/", IngestUploadAPIView.as_view(), name='ingest-upload'),

    # Token Lab — 모델/언어별 토큰 비교
    path("tokens/estimate/", TokenEstimateAPIView.as_view(), name='token-estimate'),

    # Health endpoints
    path("health/", LivenessView.as_view(), name='health-live'),
    path("health/ready/", ReadinessView.as_view(), name='health-ready'),
]
