from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Conversation, 
    ConversationParticipant, 
    Message, 
    MessageAttachment,
    MessageReadReceipt
)

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal user info for chat contexts."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'avatar', 'is_online']


class MessageAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for message attachments."""
    
    file_url = serializers.ReadOnlyField()
    
    class Meta:
        model = MessageAttachment
        fields = [
            'id', 'file', 'file_url', 'file_name', 'file_size', 
            'file_type', 'attachment_type', 'thumbnail', 
            'width', 'height', 'created_at'
        ]
        read_only_fields = ['id', 'file_url', 'created_at']


class MessageReadReceiptSerializer(serializers.ModelSerializer):
    """Serializer for read receipts."""
    
    user = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = MessageReadReceipt
        fields = ['user', 'read_at']


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages."""
    
    sender = UserMinimalSerializer(read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    read_receipts = MessageReadReceiptSerializer(many=True, read_only=True)
    is_read = serializers.SerializerMethodField()
    reply_to_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'content', 'message_type',
            'created_at', 'updated_at', 'is_edited', 'is_deleted',
            'reply_to', 'reply_to_preview', 'attachments', 
            'read_receipts', 'is_read'
        ]
        read_only_fields = [
            'id', 'sender', 'created_at', 'updated_at', 
            'is_edited', 'read_receipts'
        ]
    
    def get_is_read(self, obj):
        """Check if message is read by all participants except sender."""
        conversation = obj.conversation
        other_participants = conversation.participants.exclude(id=obj.sender.id)
        read_by = set(r.user.id for r in obj.read_receipts.all())
        return all(p.id in read_by for p in other_participants)
    
    def get_reply_to_preview(self, obj):
        """Get preview of replied message."""
        if obj.reply_to:
            return {
                'id': str(obj.reply_to.id),
                'sender': obj.reply_to.sender.username,
                'content': obj.reply_to.content[:100] if obj.reply_to.content else '',
                'message_type': obj.reply_to.message_type
            }
        return None


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new messages."""
    
    attachments = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = Message
        fields = ['conversation', 'content', 'message_type', 'reply_to', 'attachments']
    
    def validate(self, attrs):
        # Ensure either content or attachments are provided
        content = attrs.get('content', '').strip()
        attachments = attrs.get('attachments', [])
        
        if not content and not attachments:
            raise serializers.ValidationError(
                "Message must have either content or attachments."
            )
        return attrs


class ConversationParticipantSerializer(serializers.ModelSerializer):
    """Serializer for conversation participants."""
    
    user = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = ConversationParticipant
        fields = ['user', 'joined_at', 'is_admin', 'is_muted', 'last_read_at']


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for conversations."""
    
    participants = UserMinimalSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'name', 'type', 'participants', 'created_at', 
            'updated_at', 'last_message', 'unread_count', 'other_participant'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_last_message(self, obj):
        last_msg = obj.get_last_message()
        if last_msg:
            return {
                'id': str(last_msg.id),
                'content': last_msg.content[:100] if last_msg.content else '',
                'sender': last_msg.sender.username,
                'created_at': last_msg.created_at,
                'message_type': last_msg.message_type
            }
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_unread_count(request.user)
        return 0
    
    def get_other_participant(self, obj):
        """For direct messages, get the other participant's info."""
        request = self.context.get('request')
        if obj.type == 'direct' and request:
            other = obj.participants.exclude(id=request.user.id).first()
            if other:
                return UserMinimalSerializer(other).data
        return None


class ConversationCreateSerializer(serializers.Serializer):
    """Serializer for creating new conversations."""
    
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    type = serializers.ChoiceField(
        choices=['direct', 'group'],
        default='direct'
    )
    initial_message = serializers.CharField(required=False, allow_blank=True)
    
    def validate_participant_ids(self, value):
        """Validate that all participant IDs exist."""
        users = User.objects.filter(id__in=value)
        if len(users) != len(value):
            raise serializers.ValidationError("One or more user IDs are invalid.")
        return value
    
    def validate(self, attrs):
        """Validate conversation creation."""
        participant_ids = attrs.get('participant_ids', [])
        conv_type = attrs.get('type', 'direct')
        
        if conv_type == 'direct' and len(participant_ids) != 1:
            raise serializers.ValidationError(
                "Direct message must have exactly one other participant."
            )
        
        if conv_type == 'group' and len(participant_ids) < 1:
            raise serializers.ValidationError(
                "Group chat must have at least one other participant."
            )
        
        return attrs


class ConversationDetailSerializer(ConversationSerializer):
    """Detailed serializer including participant details."""
    
    participant_details = ConversationParticipantSerializer(many=True, read_only=True)
    
    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['participant_details']