from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from urllib.parse import parse_qs

User = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware for JWT authentication in WebSocket connections.
    Extracts token from query string or subprotocol.
    """
    
    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = parse_qs(scope.get('query_string', b'').decode())
        token = query_string.get('token', [None])[0]
        
        # Also check subprotocols for token
        if not token:
            subprotocols = scope.get('subprotocols', [])
            for protocol in subprotocols:
                if protocol.startswith('bearer-'):
                    token = protocol[7:]
                    break
        
        if token:
            scope['user'] = await self.get_user_from_token(token)
        else:
            # Fall back to session authentication
            scope['user'] = scope.get('user', AnonymousUser())
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def get_user_from_token(self, token):
        """Validate JWT token and return user."""
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)
            return user
        except (InvalidToken, TokenError, User.DoesNotExist):
            return AnonymousUser()