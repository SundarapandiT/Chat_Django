// Main Application
const App = {
    // Initialize application
    async init() {
        // Check if user is logged in
        if (Auth.isLoggedIn()) {
            const user = await Auth.loadUser();
            if (user) {
                this.showChat();
                return;
            }
        }

        this.showAuth();
    },

    // Show auth screens
    showAuth() {
        document.getElementById('auth-container').style.display = 'flex';
        document.getElementById('chat-container').style.display = 'none';
        this.setupAuthListeners();
    },

    // Show chat screen
    async showChat() {
        document.getElementById('auth-container').style.display = 'none';
        document.getElementById('chat-container').style.display = 'flex';

        // Update user info in sidebar
        const user = Auth.getUser();
        if (user) {
            document.getElementById('current-user-name').textContent = 
                user.full_name || user.username;
            document.getElementById('current-user-initial').textContent = 
                user.username?.charAt(0).toUpperCase() || 'U';
        }

        // Load conversations
        await Chat.loadConversations();

        // Setup chat listeners
        this.setupChatListeners();

        // Setup WebSocket listeners
        this.setupWebSocketListeners();
    },

    // Setup auth event listeners
    setupAuthListeners() {
        // Show register form
        document.getElementById('show-register').addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('login-box').style.display = 'none';
            document.getElementById('register-box').style.display = 'block';
        });

        // Show login form
        document.getElementById('show-login').addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('register-box').style.display = 'none';
            document.getElementById('login-box').style.display = 'block';
        });

        // Login form submit
        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            const errorEl = document.getElementById('login-error');
            const btn = document.getElementById('login-btn');

            btn.disabled = true;
            btn.textContent = 'Signing in...';
            errorEl.style.display = 'none';

            const result = await Auth.login(email, password);

            if (result.success) {
                this.showChat();
            } else {
                errorEl.textContent = result.error;
                errorEl.style.display = 'block';
            }

            btn.disabled = false;
            btn.textContent = 'Sign In';
        });

        // Register form submit
        document.getElementById('register-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const errorEl = document.getElementById('register-error');
            const btn = document.getElementById('register-btn');

            const userData = {
                username: document.getElementById('register-username').value,
                email: document.getElementById('register-email').value,
                password: document.getElementById('register-password').value,
                password_confirm: document.getElementById('register-password-confirm').value,
                first_name: document.getElementById('register-firstname').value,
                last_name: document.getElementById('register-lastname').value
            };

            // Validate passwords match
            if (userData.password !== userData.password_confirm) {
                errorEl.textContent = 'Passwords do not match';
                errorEl.style.display = 'block';
                return;
            }

            btn.disabled = true;
            btn.textContent = 'Creating account...';
            errorEl.style.display = 'none';

            const result = await Auth.register(userData);

            if (result.success) {
                this.showChat();
            } else {
                if (typeof result.error === 'object') {
                    const messages = Object.entries(result.error)
                        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
                        .join('\n');
                    errorEl.textContent = messages;
                } else {
                    errorEl.textContent = result.error;
                }
                errorEl.style.display = 'block';
            }

            btn.disabled = false;
            btn.textContent = 'Create Account';
        });
    },

    // Setup chat event listeners
    setupChatListeners() {
        // Logout button
        document.getElementById('logout-btn').addEventListener('click', () => {
            Auth.logout();
        });

        // New chat buttons
        document.getElementById('new-chat-btn').addEventListener('click', () => {
            this.openNewChatModal();
        });

        document.getElementById('start-new-chat-btn').addEventListener('click', () => {
            this.openNewChatModal();
        });

        // Back button (mobile)
        document.getElementById('back-btn').addEventListener('click', () => {
            document.getElementById('sidebar').classList.add('show');
        });

        // Message input
        const messageInput = document.getElementById('message-input');
        
        messageInput.addEventListener('input', () => {
            // Auto-resize
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
            
            // Typing indicator
            Chat.handleTyping();
        });

        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                Chat.sendMessage();
            }
        });

        // Send button
        document.getElementById('send-btn').addEventListener('click', () => {
            Chat.sendMessage();
        });

        // File attachment
        document.getElementById('attach-btn').addEventListener('click', () => {
            document.getElementById('file-input').click();
        });

        document.getElementById('file-input').addEventListener('change', (e) => {
            Chat.addFiles(e.target.files);
            e.target.value = '';
        });

        // Cancel reply
        document.getElementById('cancel-reply-btn').addEventListener('click', () => {
            Chat.cancelReply();
        });

        // Emoji picker
        document.getElementById('emoji-btn').addEventListener('click', () => {
            const picker = document.getElementById('emoji-picker');
            picker.style.display = picker.style.display === 'none' ? 'grid' : 'none';
        });

        document.querySelectorAll('#emoji-picker button').forEach(btn => {
            btn.addEventListener('click', () => {
                const input = document.getElementById('message-input');
                input.value += btn.textContent;
                document.getElementById('emoji-picker').style.display = 'none';
                input.focus();
            });
        });

        // Close emoji picker when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.emoji-picker-container')) {
                document.getElementById('emoji-picker').style.display = 'none';
            }
        });

        // New chat modal
        this.setupModalListeners();
    },

    // Setup modal listeners
    setupModalListeners() {
        const modal = document.getElementById('new-chat-modal');
        const searchInput = document.getElementById('user-search');
        const selectedUsers = [];
        let searchTimeout;

        // Close modal
        document.getElementById('close-modal-btn').addEventListener('click', () => {
            this.closeNewChatModal();
        });

        document.getElementById('cancel-modal-btn').addEventListener('click', () => {
            this.closeNewChatModal();
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeNewChatModal();
            }
        });

        // Search users
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(async () => {
                const query = searchInput.value.trim();
                const resultsContainer = document.getElementById('search-results');

                if (query.length < 2) {
                    resultsContainer.innerHTML = '';
                    return;
                }

                resultsContainer.innerHTML = '<div class="search-loading">Searching...</div>';

                const users = await Chat.searchUsers(query);

                if (users.length === 0) {
                    resultsContainer.innerHTML = '<div class="no-results">No users found</div>';
                    return;
                }

                resultsContainer.innerHTML = users.map(user => `
                    <div class="search-result-item ${this.modalSelectedUsers.find(u => u.id === user.id) ? 'selected' : ''}" data-id="${user.id}">
                        <div class="user-avatar">
                            ${user.avatar 
                                ? `<img src="${user.avatar}" alt="${user.username}">` 
                                : `<span>${user.username?.charAt(0).toUpperCase()}</span>`}
                        </div>
                        <div class="user-info">
                            <span class="username">${user.username}</span>
                            ${user.is_online ? '<span class="online-dot"></span>' : ''}
                        </div>
                    </div>
                `).join('');

                // Add click handlers
                resultsContainer.querySelectorAll('.search-result-item').forEach(item => {
                    item.addEventListener('click', () => {
                        const userId = parseInt(item.dataset.id);
                        const user = users.find(u => u.id === userId);
                        this.toggleUserSelection(user);
                        searchInput.value = '';
                        resultsContainer.innerHTML = '';
                    });
                });
            }, 300);
        });

        // Group chat checkbox
        document.getElementById('is-group-chat').addEventListener('change', (e) => {
            document.getElementById('group-name').style.display = e.target.checked ? 'block' : 'none';
        });

        // Create chat button
        document.getElementById('create-chat-btn').addEventListener('click', async () => {
            if (this.modalSelectedUsers.length === 0) return;

            const btn = document.getElementById('create-chat-btn');
            btn.disabled = true;
            btn.textContent = 'Creating...';

            const isGroup = this.modalSelectedUsers.length > 1 || document.getElementById('is-group-chat').checked;
            const groupName = document.getElementById('group-name').value;

            const result = await Chat.createConversation(
                this.modalSelectedUsers.map(u => u.id),
                isGroup ? groupName : '',
                isGroup ? 'group' : 'direct'
            );

            if (result.success) {
                this.closeNewChatModal();
            }

            btn.disabled = false;
            btn.textContent = 'Start Chat';
        });
    },

    // Modal selected users
    modalSelectedUsers: [],

    // Toggle user selection in modal
    toggleUserSelection(user) {
        const index = this.modalSelectedUsers.findIndex(u => u.id === user.id);
        if (index > -1) {
            this.modalSelectedUsers.splice(index, 1);
        } else {
            this.modalSelectedUsers.push(user);
        }

        this.updateSelectedUsersUI();
    },

    // Update selected users UI
    updateSelectedUsersUI() {
        const container = document.getElementById('selected-users');
        const createBtn = document.getElementById('create-chat-btn');
        const groupOptions = document.getElementById('group-options');

        container.innerHTML = this.modalSelectedUsers.map(user => `
            <div class="selected-user-chip">
                <span>${user.username}</span>
                <button onclick="App.toggleUserSelection({id: ${user.id}, username: '${user.username}'})">×</button>
            </div>
        `).join('');

        createBtn.disabled = this.modalSelectedUsers.length === 0;
        groupOptions.style.display = this.modalSelectedUsers.length > 1 ? 'block' : 'none';
    },

    // Open new chat modal
    openNewChatModal() {
        this.modalSelectedUsers = [];
        document.getElementById('user-search').value = '';
        document.getElementById('search-results').innerHTML = '';
        document.getElementById('selected-users').innerHTML = '';
        document.getElementById('group-name').value = '';
        document.getElementById('is-group-chat').checked = false;
        document.getElementById('group-name').style.display = 'none';
        document.getElementById('group-options').style.display = 'none';
        document.getElementById('create-chat-btn').disabled = true;
        document.getElementById('new-chat-modal').style.display = 'flex';
    },

    // Close new chat modal
    closeNewChatModal() {
        document.getElementById('new-chat-modal').style.display = 'none';
    },

    // Setup WebSocket listeners
    setupWebSocketListeners() {
        WebSocketService.on('new_message', (message) => {
            Chat.addMessage(message);
        });

        WebSocketService.on('typing', ({ userId, username, isTyping }) => {
            if (userId !== Auth.user?.id) {
                Chat.showTyping(userId, username, isTyping);
            }
        });

        WebSocketService.on('read_receipt', ({ userId, messageIds }) => {
            // Update message read status
            Chat.messages.forEach(msg => {
                if (messageIds.includes(msg.id)) {
                    if (!msg.read_receipts) msg.read_receipts = [];
                    msg.read_receipts.push({ user: { id: userId } });
                }
            });
            Chat.renderMessages();
        });

        WebSocketService.on('user_status', ({ userId, isOnline }) => {
            // Update online status
            if (Chat.currentConversation?.other_participant?.id === userId) {
                const statusEl = document.getElementById('chat-status');
                statusEl.textContent = isOnline ? 'Online' : 'Offline';
                statusEl.className = `status ${isOnline ? 'online' : 'offline'}`;
            }
        });

        WebSocketService.on('message_edited', ({ messageId, content }) => {
            const msg = Chat.messages.find(m => m.id === messageId);
            if (msg) {
                msg.content = content;
                msg.is_edited = true;
                Chat.renderMessages();
            }
        });

        WebSocketService.on('message_deleted', ({ messageId }) => {
            const msg = Chat.messages.find(m => m.id === messageId);
            if (msg) {
                msg.is_deleted = true;
                msg.content = '';
                Chat.renderMessages();
            }
        });
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});