from django.shortcuts import render

def chat_home(request):
    # Railway sends: X-Forwarded-Proto = 'https'
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
    
    protocol = "https" if forwarded_proto == "https" else "http"
    ws_protocol = "wss" if forwarded_proto == "https" else "ws"
    
    host = request.get_host()
    
    api_url = f"{protocol}://{host}/api"
    ws_url = f"{ws_protocol}://{host}"

    return render(request, "chat/index.html", {
        "api_url": api_url,
        "ws_url": ws_url,
    })
