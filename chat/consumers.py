import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    Conversation, 
    Message, 
    MessageReadReceipt, 
    ConversationParticipant
)
from .serializers import MessageSerializer

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat functionality.
    Handles:
    - Sending/receiving messages
    - Typing indicators
    - Read receipts
    - Online status
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        
        # Verify user is participant of this conversation
        is_participant = await self.is_conversation_participant()
        if not is_participant:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Update user online status
        await self.set_user_online(True)
        
        # Notify others that user is online
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_online': True
            }
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'user') and self.user.is_authenticated:
            # Update user online status
            await self.set_user_online(False)
            
            # Notify others that user is offline
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'user_status',
                        'user_id': self.user.id,
                        'username': self.user.username,
                        'is_online': False
                    }
                )
                
                # Leave room group
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')
            
            if message_type == 'message':
                await self.handle_chat_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'stop_typing':
                await self.handle_stop_typing(data)
            elif message_type == 'read':
                await self.handle_read_receipt(data)
            elif message_type == 'edit':
                await self.handle_edit_message(data)
            elif message_type == 'delete':
                await self.handle_delete_message(data)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            await self.send_error(str(e))
    
    async def handle_chat_message(self, data):
        """Process and broadcast a new chat message."""
        content = data.get('content', '').strip()
        reply_to_id = data.get('reply_to')
        
        if not content:
            await self.send_error("Message content is required")
            return
        
        # Save message to database
        message = await self.save_message(content, reply_to_id)
        
        if message:
            # Serialize the message
            message_data = await self.serialize_message(message)
            
            # Broadcast to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_data
                }
            )
            
            # Update conversation timestamp
            await self.update_conversation_timestamp()
    
    async def handle_typing(self, data):
        """Broadcast typing indicator."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_typing': True
            }
        )
    
    async def handle_stop_typing(self, data):
        """Broadcast stop typing indicator."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_typing': False
            }
        )
    
    async def handle_read_receipt(self, data):
        """Process read receipts for messages."""
        message_ids = data.get('message_ids', [])
        
        if not message_ids:
            return
        
        # Mark messages as read
        await self.mark_messages_read(message_ids)
        
        # Broadcast read receipts
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'read_receipt',
                'user_id': self.user.id,
                'username': self.user.username,
                'message_ids': message_ids,
                'read_at': timezone.now().isoformat()
            }
        )
    
    async def handle_edit_message(self, data):
        """Handle message editing."""
        message_id = data.get('message_id')
        new_content = data.get('content', '').strip()
        
        if not message_id or not new_content:
            await self.send_error("Message ID and content are required")
            return
        
        # Update message
        success = await self.edit_message(message_id, new_content)
        
        if success:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'content': new_content,
                    'edited_by': self.user.id,
                    'edited_at': timezone.now().isoformat()
                }
            )
    
    async def handle_delete_message(self, data):
        """Handle message deletion."""
        message_id = data.get('message_id')
        
        if not message_id:
            await self.send_error("Message ID is required")
            return
        
        # Delete message
        success = await self.delete_message(message_id)
        
        if success:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_deleted',
                    'message_id': message_id,
                    'deleted_by': self.user.id
                }
            )
    
    # Event handlers for group messages
    
    async def chat_message(self, event):
        """Send chat message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        # Don't send to the user who is typing
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing']
            }))
    
    async def read_receipt(self, event):
        """Send read receipt to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'read',
            'user_id': event['user_id'],
            'username': event['username'],
            'message_ids': event['message_ids'],
            'read_at': event['read_at']
        }))
    
    async def user_status(self, event):
        """Send user online/offline status to WebSocket."""
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'status',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_online': event['is_online']
            }))
    
    async def message_edited(self, event):
        """Send message edited notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'edited',
            'message_id': event['message_id'],
            'content': event['content'],
            'edited_by': event['edited_by'],
            'edited_at': event['edited_at']
        }))
    
    async def message_deleted(self, event):
        """Send message deleted notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'deleted',
            'message_id': event['message_id'],
            'deleted_by': event['deleted_by']
        }))
    
    async def send_error(self, error_message):
        """Send error message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message
        }))
    
    # Database operations
    
    @database_sync_to_async
    def is_conversation_participant(self):
        """Check if user is participant of the conversation."""
        return ConversationParticipant.objects.filter(
            conversation_id=self.conversation_id,
            user=self.user
        ).exists()
    
    @database_sync_to_async
    def save_message(self, content, reply_to_id=None):
        """Save a new message to the database."""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            
            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                content=content,
                message_type='text',
                reply_to_id=reply_to_id
            )
            
            return message
        except Exception as e:
            print(f"Error saving message: {e}")
            return None
    
    @database_sync_to_async
    def serialize_message(self, message):
        """Serialize message for WebSocket transmission."""
        serializer = MessageSerializer(message)
        return serializer.data
    
    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        """Mark messages as read by the current user."""
        messages = Message.objects.filter(
            id__in=message_ids,
            conversation_id=self.conversation_id
        ).exclude(sender=self.user)
        
        for message in messages:
            MessageReadReceipt.objects.get_or_create(
                message=message,
                user=self.user,
                defaults={'read_at': timezone.now()}
            )
    
    @database_sync_to_async
    def edit_message(self, message_id, new_content):
        """Edit a message (only by sender)."""
        try:
            message = Message.objects.get(
                id=message_id,
                sender=self.user,
                conversation_id=self.conversation_id
            )
            message.content = new_content
            message.is_edited = True
            message.save()
            return True
        except Message.DoesNotExist:
            return False
    
    @database_sync_to_async
    def delete_message(self, message_id):
        """Soft delete a message (only by sender)."""
        try:
            message = Message.objects.get(
                id=message_id,
                sender=self.user,
                conversation_id=self.conversation_id
            )
            message.is_deleted = True
            message.content = ""
            message.save()
            return True
        except Message.DoesNotExist:
            return False
    
    @database_sync_to_async
    def set_user_online(self, is_online):
        """Update user's online status."""
        self.user.is_online = is_online
        self.user.last_seen = timezone.now()
        self.user.save(update_fields=['is_online', 'last_seen'])
    
    @database_sync_to_async
    def update_conversation_timestamp(self):
        """Update conversation's updated_at timestamp."""
        Conversation.objects.filter(id=self.conversation_id).update(
            updated_at=timezone.now()
        )


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for user-level notifications.
    Handles notifications across all conversations.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.user_group_name = f'user_{self.user.id}'
        
        # Join user's notification group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
    
    async def new_message_notification(self, event):
        """Send new message notification."""
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'conversation_id': event['conversation_id'],
            'message': event['message']
        }))
    
    async def conversation_update(self, event):
        """Send conversation update notification."""
        await self.send(text_data=json.dumps({
            'type': 'conversation_update',
            'conversation_id': event['conversation_id'],
            'data': event['data']
        }))