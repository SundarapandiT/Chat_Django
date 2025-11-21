from django.contrib import admin
from .models import (
    Conversation, 
    ConversationParticipant, 
    Message, 
    MessageAttachment, 
    MessageReadReceipt
)


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0


class MessageAttachmentInline(admin.TabularInline):
    model = MessageAttachment
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'type', 'created_at', 'updated_at']
    list_filter = ['type', 'created_at']
    search_fields = ['name', 'participants__username']
    inlines = [ConversationParticipantInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'sender', 'conversation', 'message_type', 'created_at', 'is_deleted']
    list_filter = ['message_type', 'is_deleted', 'created_at']
    search_fields = ['content', 'sender__username']
    inlines = [MessageAttachmentInline]


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'message', 'file_name', 'attachment_type', 'file_size', 'created_at']
    list_filter = ['attachment_type', 'created_at']
    search_fields = ['file_name']


@admin.register(MessageReadReceipt)
class MessageReadReceiptAdmin(admin.ModelAdmin):
    list_display = ['message', 'user', 'read_at']
    list_filter = ['read_at']
    search_fields = ['user__username']