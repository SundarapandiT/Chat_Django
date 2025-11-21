// Chat Service
const Chat = {
    conversations: [],
    currentConversation: null,
    messages: [],
    selectedFiles: [],
    replyTo: null,
    typingTimeout: null,
    typingUsers: [],

    // Load conversations
    async loadConversations() {
        try {
            const response = await API.chat.getConversations();
            if (response.ok) {
                const data = await response.json();
                this.conversations = data.results || data;
                this.renderConversations();
            }
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    },

    // Render conversations list
    renderConversations() {
        const container = document.getElementById('conversation-list');
        
        if (this.conversations.length === 0) {
            container.innerHTML = `
                <div class="conversation-list-empty">
                    <p>No conversations yet</p>
                    <p>Start a new chat to begin messaging</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.conversations.map(conv => {
            const name = this.getConversationName(conv);
            const avatar = this.getConversationAvatar(conv);
            const lastMessage = this.getLastMessagePreview(conv);
            const time = this.formatTime(conv.last_message?.created_at || conv.updated_at);
            const isActive = this.currentConversation?.id === conv.id;
            const unreadBadge = conv.unread_count > 0 
                ? `<span class="unread-badge">${conv.unread_count}</span>` 
                : '';

            return `
                <div class="conversation-item ${isActive ? 'active' : ''}" data-id="${conv.id}">
                    <div class="conversation-avatar">
                        ${avatar}
                    </div>
                    <div class="conversation-info">
                        <div class="conversation-header">
                            <h4>${name}</h4>
                            <span class="conversation-time">${time}</span>
                        </div>
                        <div class="conversation-preview">
                            <p>${lastMessage}</p>
                            ${unreadBadge}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Add click handlers
        container.querySelectorAll('.conversation-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = parseInt(item.dataset.id);
                const conv = this.conversations.find(c => c.id === id);
                if (conv) this.selectConversation(conv);
            });
        });
    },

    // Get conversation name
    getConversationName(conv) {
        if (conv.name) return conv.name;
        if (conv.type === 'direct' && conv.other_participant) {
            return conv.other_participant.username;
        }
        const participants = conv.participants?.filter(p => p.id !== Auth.user?.id) || [];
        return participants.map(p => p.username).join(', ') || 'Unknown';
    },

    // Get conversation avatar
    getConversationAvatar(conv) {
        if (conv.type === 'direct' && conv.other_participant) {
            if (conv.other_participant.avatar) {
                return `<img src="${conv.other_participant.avatar}" alt="">`;
            }
            return conv.other_participant.username?.charAt(0).toUpperCase() || 'U';
        }
        return '👥';
    },

    // Get last message preview
    getLastMessagePreview(conv) {
        const lastMsg = conv.last_message;
        if (!lastMsg) return 'No messages yet';

        let preview = '';
        if (lastMsg.message_type === 'image') {
            preview = '📷 Photo';
        } else if (lastMsg.message_type === 'file') {
            preview = '📎 File';
        } else {
            preview = lastMsg.content || '';
        }

        if (conv.type === 'group') {
            preview = `${lastMsg.sender}: ${preview}`;
        }

        return preview.length > 40 ? preview.substring(0, 40) + '...' : preview;
    },

    // Format time
    formatTime(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) return 'now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)}d`;

        return date.toLocaleDateString();
    },

    // Select a conversation
    async selectConversation(conversation) {
        // Disconnect from previous
        if (this.currentConversation) {
            WebSocketService.disconnect();
        }

        this.currentConversation = conversation;
        this.messages = [];
        this.typingUsers = [];
        this.replyTo = null;

        // Update UI
        document.getElementById('no-chat-selected').style.display = 'none';
        document.getElementById('chat-window').style.display = 'flex';

        // Update header
        document.getElementById('chat-title').textContent = this.getConversationName(conversation);
        
        const statusEl = document.getElementById('chat-status');
        if (conversation.type === 'direct' && conversation.other_participant) {
            statusEl.textContent = conversation.other_participant.is_online ? 'Online' : 'Offline';
            statusEl.className = `status ${conversation.other_participant.is_online ? 'online' : 'offline'}`;
        } else {
            statusEl.textContent = `${conversation.participants?.length || 0} participants`;
            statusEl.className = 'status';
        }

        // Load messages
        await this.loadMessages(conversation.id);

        // Connect WebSocket
        WebSocketService.connect(conversation.id);

        // Update conversation list
        this.renderConversations();

        // Hide sidebar on mobile
        document.getElementById('sidebar').classList.remove('show');
    },

    // Load messages
    async loadMessages(conversationId) {
        const container = document.getElementById('messages-container');
        container.innerHTML = '<div class="loading-messages"><div class="loading-spinner"></div><p>Loading messages...</p></div>';

        try {
            const response = await API.chat.getMessages(conversationId);
            if (response.ok) {
                const data = await response.json();
                this.messages = data.results || data;
                this.renderMessages();
            }
        } catch (error) {
            console.error('Failed to load messages:', error);
            container.innerHTML = '<div class="no-messages"><p>Failed to load messages</p></div>';
        }
    },

    // Render messages
    renderMessages() {
        const container = document.getElementById('messages-container');

        if (this.messages.length === 0) {
            container.innerHTML = '<div class="no-messages"><p>No messages yet. Start the conversation!</p></div>';
            return;
        }

        // Group messages by date
        const grouped = {};
        this.messages.forEach(msg => {
            const date = new Date(msg.created_at).toDateString();
            if (!grouped[date]) grouped[date] = [];
            grouped[date].push(msg);
        });

        let html = '';
        Object.entries(grouped).forEach(([date, messages]) => {
            html += `<div class="date-divider"><span>${this.formatDate(date)}</span></div>`;
            messages.forEach(msg => {
                html += this.renderMessage(msg);
            });
        });

        container.innerHTML = html;

        // Add reply handlers
        container.querySelectorAll('.reply-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const msgId = btn.dataset.id;
                const msg = this.messages.find(m => m.id === msgId);
                if (msg) this.setReplyTo(msg);
            });
        });

        // Scroll to bottom
        container.scrollTop = container.scrollHeight;
    },

    // Render single message
    renderMessage(msg) {
        const isOwn = msg.sender.id === Auth.user?.id;
        const isDeleted = msg.is_deleted;

        if (isDeleted) {
            return `
                <div class="message ${isOwn ? 'own' : ''} deleted">
                    <div class="message-bubble">
                        <em>This message was deleted</em>
                    </div>
                </div>
            `;
        }

        const avatar = isOwn ? '' : `
            <div class="message-avatar">
                ${msg.sender.avatar 
                    ? `<img src="${msg.sender.avatar}" alt="${msg.sender.username}">` 
                    : msg.sender.username?.charAt(0).toUpperCase()}
            </div>
        `;

        const sender = isOwn ? '' : `<span class="message-sender">${msg.sender.username}</span>`;

        const replyPreview = msg.reply_to_preview ? `
            <div class="message-reply-preview">
                <span class="reply-sender">${msg.reply_to_preview.sender}</span>
                <span class="reply-content">${msg.reply_to_preview.content || 'Attachment'}</span>
            </div>
        ` : '';

        const content = msg.content ? `<p class="message-text">${this.escapeHtml(msg.content)}</p>` : '';

        const attachments = this.renderAttachments(msg.attachments);

        const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const edited = msg.is_edited ? '<span class="edited-label">edited</span>' : '';

        const readStatus = isOwn ? this.renderReadStatus(msg) : '';

        return `
            <div class="message ${isOwn ? 'own' : ''}">
                ${avatar}
                <div class="message-bubble">
                    ${sender}
                    ${replyPreview}
                    ${content}
                    ${attachments}
                    <div class="message-meta">
                        <span class="message-time">${time}</span>
                        ${edited}
                        ${readStatus}
                    </div>
                </div>
                <div class="message-actions">
                    <button class="action-button reply-btn" data-id="${msg.id}" title="Reply">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                            <path d="M10 9V5l-7 7 7 7v-4.1c5 0 8.5 1.6 11 5.1-1-5-4-10-11-11z"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
    },

    // Render attachments
    renderAttachments(attachments) {
        if (!attachments || attachments.length === 0) return '';

        return `
            <div class="message-attachments">
                ${attachments.map(att => {
                    if (att.attachment_type === 'image') {
                        return `<img src="${att.file_url || att.file}" alt="${att.file_name}" class="attachment-image" onclick="window.open('${att.file_url || att.file}', '_blank')">`;
                    } else {
                        const icon = this.getFileIcon(att.attachment_type);
                        const size = this.formatFileSize(att.file_size);
                        return `
                            <a href="${att.file_url || att.file}" target="_blank" class="attachment-file">
                                <span class="file-icon">${icon}</span>
                                <div class="file-info">
                                    <span class="file-name">${att.file_name}</span>
                                    <span class="file-size">${size}</span>
                                </div>
                            </a>
                        `;
                    }
                }).join('')}
            </div>
        `;
    },

    // Get file icon
    getFileIcon(type) {
        switch (type) {
            case 'document': return '📄';
            case 'video': return '🎬';
            case 'audio': return '🎵';
            default: return '📎';
        }
    },

    // Format file size
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // Render read status
    renderReadStatus(msg) {
        const readCount = msg.read_receipts?.length || 0;
        if (readCount > 0) {
            return `
                <span class="read-status">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="#4caf50">
                        <path d="M18 7l-1.41-1.41-6.34 6.34 1.41 1.41L18 7zm4.24-1.41L11.66 16.17 7.48 12l-1.41 1.41L11.66 19l12-12-1.42-1.41zM.41 13.41L6 19l1.41-1.41L1.83 12 .41 13.41z"/>
                    </svg>
                </span>
            `;
        }
        return `
            <span class="read-status">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="#999">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
            </span>
        `;
    },

    // Format date
    formatDate(dateString) {
        const date = new Date(dateString);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        if (date.toDateString() === today.toDateString()) return 'Today';
        if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';

        return date.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    },

    // Escape HTML
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    // Set reply to
    setReplyTo(msg) {
        this.replyTo = msg;
        document.getElementById('reply-bar').style.display = 'flex';
        document.getElementById('reply-sender').textContent = msg.sender.username;
        document.getElementById('reply-text').textContent = msg.content?.substring(0, 50) || 'Attachment';
        document.getElementById('message-input').focus();
    },

    // Cancel reply
    cancelReply() {
        this.replyTo = null;
        document.getElementById('reply-bar').style.display = 'none';
    },

    // Send message
    async sendMessage() {
        const input = document.getElementById('message-input');
        const content = input.value.trim();

        if (!content && this.selectedFiles.length === 0) return;
        if (!this.currentConversation) return;

        // Clear typing indicator
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
            WebSocketService.sendStopTyping();
        }

        if (this.selectedFiles.length > 0) {
            // Send with attachments via HTTP
            const formData = new FormData();
            formData.append('content', content);
            this.selectedFiles.forEach(file => {
                formData.append('attachments', file);
            });
            if (this.replyTo) {
                formData.append('reply_to', this.replyTo.id);
            }

            try {
                const response = await API.chat.sendMessage(this.currentConversation.id, formData);
                if (response.ok) {
                    // Message will come through WebSocket
                }
            } catch (error) {
                console.error('Failed to send message:', error);
            }
        } else {
            // Send text via WebSocket
            WebSocketService.sendMessage(content, this.replyTo?.id);
        }

        // Clear input
        input.value = '';
        input.style.height = 'auto';
        this.selectedFiles = [];
        this.renderFilePreview();
        this.cancelReply();
    },

    // Handle typing
    handleTyping() {
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
        } else {
            WebSocketService.sendTyping();
        }

        this.typingTimeout = setTimeout(() => {
            WebSocketService.sendStopTyping();
            this.typingTimeout = null;
        }, 2000);
    },

    // Add file
    addFiles(files) {
        this.selectedFiles = [...this.selectedFiles, ...Array.from(files)];
        this.renderFilePreview();
    },

    // Remove file
    removeFile(index) {
        this.selectedFiles.splice(index, 1);
        this.renderFilePreview();
    },

    // Render file preview
    renderFilePreview() {
        const container = document.getElementById('file-preview-container');

        if (this.selectedFiles.length === 0) {
            container.style.display = 'none';
            container.innerHTML = '';
            return;
        }

        container.style.display = 'flex';
        container.innerHTML = this.selectedFiles.map((file, index) => {
            if (file.type.startsWith('image/')) {
                return `
                    <div class="file-preview">
                        <img src="${URL.createObjectURL(file)}" alt="${file.name}">
                        <button class="remove-file" onclick="Chat.removeFile(${index})">×</button>
                    </div>
                `;
            } else {
                return `
                    <div class="file-preview">
                        <div class="file-preview-icon">📎</div>
                        <span class="file-name">${file.name}</span>
                        <button class="remove-file" onclick="Chat.removeFile(${index})">×</button>
                    </div>
                `;
            }
        }).join('');
    },

    // Add new message (from WebSocket)
    addMessage(msg) {
        this.messages.push(msg);
        this.renderMessages();

        // Auto-mark as read if from another user
        if (msg.sender.id !== Auth.user?.id) {
            WebSocketService.sendReadReceipt([msg.id]);
        }

        // Update conversation list
        const conv = this.conversations.find(c => c.id === this.currentConversation?.id);
        if (conv) {
            conv.last_message = {
                id: msg.id,
                content: msg.content,
                sender: msg.sender.username,
                created_at: msg.created_at,
                message_type: msg.message_type
            };
            this.renderConversations();
        }
    },

    // Show typing indicator
    showTyping(userId, username, isTyping) {
        if (isTyping) {
            if (!this.typingUsers.find(u => u.id === userId)) {
                this.typingUsers.push({ id: userId, username });
            }

            // Auto-clear after 3 seconds
            setTimeout(() => {
                this.typingUsers = this.typingUsers.filter(u => u.id !== userId);
                this.updateTypingIndicator();
            }, 3000);
        } else {
            this.typingUsers = this.typingUsers.filter(u => u.id !== userId);
        }

        this.updateTypingIndicator();
    },

    // Update typing indicator
    updateTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        const text = document.getElementById('typing-text');

        if (this.typingUsers.length > 0) {
            const names = this.typingUsers.map(u => u.username).join(', ');
            text.textContent = `${names} ${this.typingUsers.length === 1 ? 'is' : 'are'} typing...`;
            indicator.style.display = 'flex';
        } else {
            indicator.style.display = 'none';
        }
    },

    // Create conversation
    async createConversation(participantIds, name = '', type = 'direct') {
        try {
            const response = await API.chat.createConversation({
                participant_ids: participantIds,
                name,
                type
            });

            if (response.ok) {
                const conv = await response.json();
                this.conversations.unshift(conv);
                this.renderConversations();
                await this.selectConversation(conv);
                return { success: true, conversation: conv };
            } else {
                const error = await response.json();
                return { success: false, error };
            }
        } catch (error) {
            return { success: false, error: 'Network error' };
        }
    },

    // Search users
    // Search users
async searchUsers(query) {
    if (query.length < 2) return [];

    try {
        const response = await API.auth.searchUsers(query);
        if (response.ok) {
            const data = await response.json();
            console.log('Search users data:', data);
            // Handle paginated response
            return data.results || data;
        }
    } catch (error) {
        console.error('Failed to search users:', error);
    }

    return [];
}
};