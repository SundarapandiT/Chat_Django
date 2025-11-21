from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Conversations
    path('conversations/', views.ConversationListView.as_view(), name='conversation-list'),
    path('conversations/create/', views.ConversationCreateView.as_view(), name='conversation-create'),
    path('conversations/<int:pk>/', views.ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<int:conversation_id>/participants/', views.ConversationParticipantsView.as_view(), name='conversation-participants'),
    
    # Messages
    path('conversations/<int:conversation_id>/messages/', views.MessageListView.as_view(), name='message-list'),
    path('conversations/<int:conversation_id>/messages/create/', views.MessageCreateView.as_view(), name='message-create'),
    path('conversations/<int:conversation_id>/messages/read/', views.MarkMessagesReadView.as_view(), name='mark-read'),
    
    # Utilities
    path('unread-count/', views.UnreadCountView.as_view(), name='unread-count'),
]