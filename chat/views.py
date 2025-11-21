import os
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q, Max, Count
from django.shortcuts import get_object_or_404
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import (
    Conversation, 
    ConversationParticipant,
    Message, 
    MessageAttachment,
    MessageReadReceipt
)
from .serializers import (
    ConversationSerializer,
    ConversationDetailSerializer,
    ConversationCreateSerializer,
    MessageSerializer,
    MessageCreateSerializer,
    MessageAttachmentSerializer,
)


class ConversationListView(generics.ListAPIView):
    """
    API endpoint to list all conversations for the current user.
    Ordered by most recent activity.
    """
    
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Conversation.objects.filter(
            participants=self.request.user
        ).annotate(
            last_activity=Max('messages__created_at')
        ).order_by('-last_activity', '-updated_at')


class ConversationCreateView(APIView):
    """
    API endpoint to create a new conversation.
    Handles both direct messages and group chats.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        participant_ids = serializer.validated_data['participant_ids']
        conv_type = serializer.validated_data.get('type', 'direct')
        name = serializer.validated_data.get('name', '')
        initial_message = serializer.validated_data.get('initial_message', '')
        
        # For direct messages, check if conversation already exists
        if conv_type == 'direct':
            other_user_id = participant_ids[0]
            existing = Conversation.objects.filter(
                type='direct',
                participants=request.user
            ).filter(
                participants=other_user_id
            ).first()
            
            if existing:
                return Response(
                    ConversationSerializer(existing, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
        
        # Create new conversation
        conversation = Conversation.objects.create(
            name=name if conv_type == 'group' else '',
            type=conv_type
        )
        
        # Add current user as participant (and admin for groups)
        ConversationParticipant.objects.create(
            conversation=conversation,
            user=request.user,
            is_admin=(conv_type == 'group')
        )
        
        # Add other participants
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        for user_id in participant_ids:
            user = User.objects.get(id=user_id)
            ConversationParticipant.objects.create(
                conversation=conversation,
                user=user
            )
        
        # Send initial message if provided
        if initial_message:
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=initial_message,
                message_type='text'
            )
        
        return Response(
            ConversationSerializer(conversation, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ConversationDetailView(generics.RetrieveAPIView):
    """
    API endpoint to get details of a specific conversation.
    """
    
    serializer_class = ConversationDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user)


class MessageListView(generics.ListAPIView):
    """
    API endpoint to list messages in a conversation.
    Supports pagination and marking messages as read.
    """
    
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        conversation_id = self.kwargs['conversation_id']
        
        # Verify user is participant
        conversation = get_object_or_404(
            Conversation.objects.filter(participants=self.request.user),
            id=conversation_id
        )
        
        # Mark messages as read when fetching
        unread_messages = conversation.messages.exclude(
            sender=self.request.user
        ).exclude(
            read_receipts__user=self.request.user
        )
        
        for message in unread_messages:
            MessageReadReceipt.objects.get_or_create(
                message=message,
                user=self.request.user
            )
        
        return conversation.messages.filter(
            is_deleted=False
        ).select_related(
            'sender'
        ).prefetch_related(
            'attachments', 'read_receipts__user'
        )


class MessageCreateView(APIView):
    """
    API endpoint to create a new message with optional attachments.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, conversation_id):
        # Verify user is participant
        conversation = get_object_or_404(
            Conversation.objects.filter(participants=request.user),
            id=conversation_id
        )
        
        content = request.data.get('content', '').strip()
        reply_to_id = request.data.get('reply_to')
        files = request.FILES.getlist('attachments')
        
        if not content and not files:
            return Response(
                {'error': 'Message must have content or attachments'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine message type
        message_type = 'text'
        if files:
            # Check first file to determine type
            first_file = files[0]
            if first_file.content_type.startswith('image/'):
                message_type = 'image'
            else:
                message_type = 'file'
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content,
            message_type=message_type,
            reply_to_id=reply_to_id
        )
        
        # Process attachments
        for file in files:
            # Validate file
            file_ext = os.path.splitext(file.name)[1].lower()
            
            if file_ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
                message.delete()
                return Response(
                    {'error': f'File type {file_ext} is not allowed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if file.size > settings.MAX_UPLOAD_SIZE:
                message.delete()
                return Response(
                    {'error': f'File size exceeds limit of {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Determine attachment type
            attachment_type = self.get_attachment_type(file.content_type)
            
            # Create attachment
            MessageAttachment.objects.create(
                message=message,
                file=file,
                file_name=file.name,
                file_size=file.size,
                file_type=file.content_type,
                attachment_type=attachment_type
            )
        
        # Update conversation timestamp
        conversation.save()  # Updates updated_at
        
        # Broadcast message via WebSocket
        channel_layer = get_channel_layer()
        message_data = MessageSerializer(message).data
        
        async_to_sync(channel_layer.group_send)(
            f'chat_{conversation_id}',
            {
                'type': 'chat_message',
                'message': message_data
            }
        )
        
        # Notify other participants
        for participant in conversation.participants.exclude(id=request.user.id):
            async_to_sync(channel_layer.group_send)(
                f'user_{participant.id}',
                {
                    'type': 'new_message_notification',
                    'conversation_id': conversation_id,
                    'message': message_data
                }
            )
        
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED
        )
    
    def get_attachment_type(self, content_type):
        """Determine attachment type from MIME type."""
        if content_type.startswith('image/'):
            return 'image'
        elif content_type.startswith('video/'):
            return 'video'
        elif content_type.startswith('audio/'):
            return 'audio'
        elif content_type in ['application/pdf', 'application/msword', 
                               'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                               'text/plain']:
            return 'document'
        return 'other'


class MarkMessagesReadView(APIView):
    """
    API endpoint to mark specific messages as read.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, conversation_id):
        message_ids = request.data.get('message_ids', [])
        
        if not message_ids:
            return Response(
                {'error': 'message_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify user is participant
        conversation = get_object_or_404(
            Conversation.objects.filter(participants=request.user),
            id=conversation_id
        )
        
        # Mark messages as read
        messages = Message.objects.filter(
            id__in=message_ids,
            conversation=conversation
        ).exclude(sender=request.user)
        
        read_count = 0
        for message in messages:
            _, created = MessageReadReceipt.objects.get_or_create(
                message=message,
                user=request.user
            )
            if created:
                read_count += 1
        
        # Broadcast read receipts via WebSocket
        if read_count > 0:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{conversation_id}',
                {
                    'type': 'read_receipt',
                    'user_id': request.user.id,
                    'username': request.user.username,
                    'message_ids': [str(m.id) for m in messages],
                    'read_at': MessageReadReceipt.objects.filter(
                        user=request.user,
                        message__in=messages
                    ).first().read_at.isoformat() if messages else None
                }
            )
        
        return Response({
            'marked_read': read_count
        })


class ConversationParticipantsView(APIView):
    """
    API endpoint to manage conversation participants (for group chats).
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, conversation_id):
        """Add participants to a group chat."""
        conversation = get_object_or_404(
            Conversation.objects.filter(
                participants=request.user,
                type='group'
            ),
            id=conversation_id
        )
        
        # Check if user is admin
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            user=request.user
        )
        
        if not participant.is_admin:
            return Response(
                {'error': 'Only admins can add participants'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user_ids = request.data.get('user_ids', [])
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        added = []
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                _, created = ConversationParticipant.objects.get_or_create(
                    conversation=conversation,
                    user=user
                )
                if created:
                    added.append(user_id)
                    
                    # Create system message
                    Message.objects.create(
                        conversation=conversation,
                        sender=request.user,
                        content=f"{user.username} was added to the group",
                        message_type='system'
                    )
            except User.DoesNotExist:
                pass
        
        return Response({'added': added})
    
    def delete(self, request, conversation_id):
        """Remove a participant from a group chat."""
        conversation = get_object_or_404(
            Conversation.objects.filter(
                participants=request.user,
                type='group'
            ),
            id=conversation_id
        )
        
        user_id = request.data.get('user_id')
        
        # Users can remove themselves, admins can remove others
        if user_id == request.user.id:
            ConversationParticipant.objects.filter(
                conversation=conversation,
                user=request.user
            ).delete()
            
            return Response({'removed': user_id})
        
        # Check if user is admin
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            user=request.user
        )
        
        if not participant.is_admin:
            return Response(
                {'error': 'Only admins can remove other participants'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ConversationParticipant.objects.filter(
            conversation=conversation,
            user_id=user_id
        ).delete()
        
        return Response({'removed': user_id})


class UnreadCountView(APIView):
    """
    API endpoint to get total unread message count across all conversations.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        conversations = Conversation.objects.filter(participants=request.user)
        
        total_unread = 0
        for conv in conversations:
            total_unread += conv.get_unread_count(request.user)
        
        return Response({
            'total_unread': total_unread
        })