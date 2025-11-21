// API Service
const API = {
    // Get auth headers
    getHeaders() {
        const token = localStorage.getItem('access_token');
        return {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` })
        };
    },

    // Generic fetch wrapper with token refresh
    async fetch(url, options = {}) {
        const response = await fetch(`${CONFIG.API_URL}${url}`, {
            ...options,
            headers: {
                ...this.getHeaders(),
                ...options.headers
            }
        });

        // If unauthorized, try to refresh token
        if (response.status === 401) {
            const refreshed = await this.refreshToken();
            if (refreshed) {
                // Retry the request
                return fetch(`${CONFIG.API_URL}${url}`, {
                    ...options,
                    headers: {
                        ...this.getHeaders(),
                        ...options.headers
                    }
                });
            } else {
                // Logout user
                Auth.logout();
                return response;
            }
        }

        return response;
    },

    // Refresh access token
    async refreshToken() {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) return false;

        try {
            const response = await fetch(`${CONFIG.API_URL}/token/refresh/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh: refreshToken })
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access);
                return true;
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
        }

        return false;
    },

    // Auth endpoints
    auth: {
        async login(email, password) {
            const response = await fetch(`${CONFIG.API_URL}/token/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            return response;
        },

        async register(userData) {
            const response = await fetch(`${CONFIG.API_URL}/auth/register/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(userData)
            });
            return response;
        },

        async getProfile() {
            return API.fetch('/auth/profile/');
        },

        async searchUsers(query) {
            return API.fetch(`/auth/users/search/?q=${encodeURIComponent(query)}`);
        },

        async getUsers() {
            return API.fetch('/auth/users/');
        }
    },

    // Chat endpoints
    chat: {
        async getConversations() {
            return API.fetch('/chat/conversations/');
        },

        async createConversation(data) {
            return API.fetch('/chat/conversations/create/', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        async getConversation(id) {
            return API.fetch(`/chat/conversations/${id}/`);
        },

        async getMessages(conversationId, page = 1) {
            return API.fetch(`/chat/conversations/${conversationId}/messages/?page=${page}`);
        },

        async sendMessage(conversationId, formData) {
            const token = localStorage.getItem('access_token');
            return fetch(`${CONFIG.API_URL}/chat/conversations/${conversationId}/messages/create/`, {
                method: 'POST',
                headers: {
                    ...(token && { 'Authorization': `Bearer ${token}` })
                },
                body: formData
            });
        },

        async markAsRead(conversationId, messageIds) {
            return API.fetch(`/chat/conversations/${conversationId}/messages/read/`, {
                method: 'POST',
                body: JSON.stringify({ message_ids: messageIds })
            });
        },

        async getUnreadCount() {
            return API.fetch('/chat/unread-count/');
        }
    }
};