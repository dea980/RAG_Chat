from django.urls import path
from . import views
from .auth_views import LoginAPIView, LogoutAPIView, MeAPIView
from .health import LivenessView, ReadinessView
from .compare_views import ChatCompareAPIView
from .conversation_views import (
    ConversationDetailAPIView,
    ConversationListAPIView,
    MessageCreateAPIView,
)
from .embedding_views import EmbeddingCompareAPIView, EmbeddingEvalAPIView
from .ingest_views import IngestPreviewAPIView, IngestUploadAPIView
from .token_views import TokenEstimateAPIView, TokenTestSetsAPIView

urlpatterns = [
    # Auth — session-based login/logout (B3)
    path("auth/login/", LoginAPIView.as_view(), name='auth-login'),
    path("auth/logout/", LogoutAPIView.as_view(), name='auth-logout'),
    path("auth/me/", MeAPIView.as_view(), name='auth-me'),

    path("chat/", views.ChatAPIView.as_view(), name='chat-create'),
    path("chat-user/", views.ChatUserAPIView.as_view(), name='chat-user'),
    path("chat-rag/", views.ChatRagAPIView.as_view(), name='chat-rag'),

    # ChatGPT-style multi-turn conversations + attachments (multipart)
    path("conversations/", ConversationListAPIView.as_view(), name='conversation-list'),
    path("conversations/<uuid:conv_id>/", ConversationDetailAPIView.as_view(), name='conversation-detail'),
    path("messages/", MessageCreateAPIView.as_view(), name='message-create'),
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
    path("tokens/test-sets/", TokenTestSetsAPIView.as_view(), name='token-test-sets'),

    # Chat Compare lab — 같은 프롬프트를 N개 모델에 동시 호출 (RAG/moderation 우회)
    path("chat/compare/", ChatCompareAPIView.as_view(), name='chat-compare'),

    # Embedding Lab — Mode A (Pair Compare): 두 텍스트의 모델별 유사도
    path("embeddings/compare/", EmbeddingCompareAPIView.as_view(), name='embedding-compare'),

    # Embedding Lab — Mode B (Benchmark Eval): KorSTS/KorNLI/curated 벌크 평가
    path("embeddings/eval/", EmbeddingEvalAPIView.as_view(), name='embedding-eval'),

    # Health endpoints
    path("health/", LivenessView.as_view(), name='health-live'),
    path("health/ready/", ReadinessView.as_view(), name='health-ready'),
]
