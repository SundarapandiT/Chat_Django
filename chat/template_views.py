from django.shortcuts import render
from django.conf import settings


def chat_home(request):
    """Serve the main chat application."""
    
    # Determine API and WebSocket URLs
    if settings.DEBUG:
        api_url = 'http://localhost:8000/api'
        ws_url = 'wss://localhost:8000'
    else:
        # For production, use the same host
        host = request.get_host()
        protocol = 'https' if request.is_secure() else 'http'
        ws_protocol = 'wss' if request.is_secure() else 'ws'
        api_url = f'{protocol}://{host}/api'
        ws_url = f'{ws_protocol}://{host}'
    
    context = {
        'api_url': api_url,
        'ws_url': ws_url,
    }
    
    return render(request, 'chat/index.html', context)