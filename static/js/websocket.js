// WebSocket Service
const WebSocketService = {
    socket: null,
    conversationId: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    listeners: {},

    // Connect to a conversation
    connect(conversationId) {
        const token = localStorage.getItem('access_token');
        if (!token) {
            console.error('No auth token found');
            return;
        }

        this.conversationId = conversationId;
        const url = `${CONFIG.WS_URL}/ws/chat/${conversationId}/?token=${token}`;

        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.emit('connected', { conversationId });
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        this.socket.onclose = (event) => {
            console.log('WebSocket closed:', event.code);
            this.emit('disconnected', { conversationId });

            // Attempt to reconnect
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                setTimeout(() => {
                    this.reconnectAttempts++;
                    this.connect(conversationId);
                }, 1000 * this.reconnectAttempts);
            }
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.emit('error', error);
        };
    },

    // Disconnect
    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
            this.conversationId = null;
        }
    },

    // Handle incoming messages
    handleMessage(data) {
        const { type } = data;

        switch (type) {
            case 'message':
                this.emit('new_message', data.message);
                break;
            case 'typing':
                this.emit('typing', {
                    userId: data.user_id,
                    username: data.username,
                    isTyping: data.is_typing
                });
                break;
            case 'read':
                this.emit('read_receipt', {
                    userId: data.user_id,
                    username: data.username,
                    messageIds: data.message_ids,
                    readAt: data.read_at
                });
                break;
            case 'status':
                this.emit('user_status', {
                    userId: data.user_id,
                    username: data.username,
                    isOnline: data.is_online
                });
                break;
            case 'edited':
                this.emit('message_edited', {
                    messageId: data.message_id,
                    content: data.content,
                    editedAt: data.edited_at
                });
                break;
            case 'deleted':
                this.emit('message_deleted', {
                    messageId: data.message_id
                });
                break;
            case 'error':
                this.emit('error', { message: data.message });
                break;
        }
    },

    // Send message
    sendMessage(content, replyTo = null) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: 'message',
                content,
                reply_to: replyTo
            }));
        }
    },

    // Send typing indicator
    sendTyping() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type: 'typing' }));
        }
    },

    // Send stop typing
    sendStopTyping() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type: 'stop_typing' }));
        }
    },

    // Send read receipts
    sendReadReceipt(messageIds) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: 'read',
                message_ids: messageIds
            }));
        }
    },

    // Event listener management
    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    },

    off(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
        }
    },

    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => callback(data));
        }
    },

    // Check connection status
    isConnected() {
        return this.socket && this.socket.readyState === WebSocket.OPEN;
    }
};