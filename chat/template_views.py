from django.shortcuts import render

def chat_home(request):
    # Detect host and protocol automatically
    host = request.get_host() #https://web-production-8ccaa.up.railway.app/

    is_secure = request.is_secure()
    protocol = "https" if is_secure else "http"
    ws_protocol = "wss" if is_secure else "ws"

    api_url = f"{protocol}://{host}/api"
    ws_url = f"{ws_protocol}://{host}"

    return render(request, "chat/index.html", {
        "api_url": api_url,
        "ws_url": ws_url,
    })
