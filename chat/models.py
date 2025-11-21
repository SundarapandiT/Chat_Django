import os
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


def message_attachment_path(instance, filename):
    """Generate unique path for message attachments."""
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4()}{ext}"
    return f"attachments/{instance.message.conversation.id}/{new_filename}"


class Conversation(models.Model):
    """
    Represents a chat conversation between users.
    Can be direct (1-1) or group chat.
    """
    
    CONVERSATION_TYPES = [
        ('direct', 'Direct Message'),
        ('group', 'Group Chat'),
    ]
    
    name = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=10, choices=CONVERSATION_TYPES, default='direct')
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='conversations',
        through='ConversationParticipant'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'conversations'
        ordering = ['-updated_at']
    
    def __str__(self):
        if self.name:
            return self.name
        participant_names = ', '.join([p.username for p in self.participants.all()[:3]])
        return f"Conversation: {participant_names}"
    
    def get_last_message(self):
        return self.messages.order_by('-created_at').first()
    
    def get_unread_count(self, user):
        """Get count of unread messages for a specific user."""
        return self.messages.exclude(
            sender=user
        ).exclude(
            read_receipts__user=user
        ).count()


class ConversationParticipant(models.Model):
    """Through model for conversation participants with additional metadata."""
    
    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE,
        related_name='participant_details'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='conversation_memberships'
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)  # For group chats
    is_muted = models.BooleanField(default=False)
    last_read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'conversation_participants'
        unique_together = ['conversation', 'user']
    
    def __str__(self):
        return f"{self.user.username} in {self.conversation}"


class Message(models.Model):
    """
    Represents a single message in a conversation.
    Supports text content and file attachments.
    """
    
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),  # For notifications like "User joined"
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sent_messages'
    )
    content = models.TextField(blank=True)
    message_type = models.CharField(
        max_length=10, 
        choices=MESSAGE_TYPES, 
        default='text'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    # Reply functionality
    reply_to = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='replies'
    )
    
    class Meta:
        db_table = 'messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"
    
    def mark_as_read(self, user):
        """Mark this message as read by a user."""
        if user != self.sender:
            MessageReadReceipt.objects.get_or_create(
                message=self,
                user=user,
                defaults={'read_at': timezone.now()}
            )
    
    def is_read_by(self, user):
        """Check if message has been read by a specific user."""
        return self.read_receipts.filter(user=user).exists()
    
    def get_read_by_users(self):
        """Get list of users who have read this message."""
        return [receipt.user for receipt in self.read_receipts.all()]


class MessageAttachment(models.Model):
    """
    Represents a file attachment for a message.
    Supports images, PDFs, documents, etc.
    """
    
    ATTACHMENT_TYPES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message, 
        on_delete=models.CASCADE, 
        related_name='attachments'
    )
    file = models.FileField(upload_to=message_attachment_path)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()  # in bytes
    file_type = models.CharField(max_length=100)  # MIME type
    attachment_type = models.CharField(
        max_length=20, 
        choices=ATTACHMENT_TYPES, 
        default='other'
    )
    
    # For images - thumbnail generation
    thumbnail = models.ImageField(
        upload_to='thumbnails/', 
        null=True, 
        blank=True
    )
    
    # Image dimensions (optional)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'message_attachments'
    
    def __str__(self):
        return f"{self.file_name} ({self.attachment_type})"
    
    @property
    def file_url(self):
        if self.file:
            return self.file.url
        return None


class MessageReadReceipt(models.Model):
    """
    Tracks when users read messages.
    Enables 'seen' functionality.
    """
    
    message = models.ForeignKey(
        Message, 
        on_delete=models.CASCADE, 
        related_name='read_receipts'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='read_receipts'
    )
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'message_read_receipts'
        unique_together = ['message', 'user']
    
    def __str__(self):
        return f"{self.user.username} read {self.message.id}"


class TypingStatus(models.Model):
    """
    Tracks typing status for real-time 'user is typing' indicators.
    This is typically handled in-memory via Redis, but can be persisted if needed.
    """
    
    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE,
        related_name='typing_statuses'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE
    )
    started_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'typing_statuses'
        unique_together = ['conversation', 'user']