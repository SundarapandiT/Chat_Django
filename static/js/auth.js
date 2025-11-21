// Authentication Service
const Auth = {
    user: null,

    // Check if user is logged in
    isLoggedIn() {
        return !!localStorage.getItem('access_token');
    },

    // Login
    async login(email, password) {
        try {
            const response = await API.auth.login(email, password);
            const data = await response.json();

            if (response.ok) {
                localStorage.setItem('access_token', data.access);
                localStorage.setItem('refresh_token', data.refresh);
                await this.loadUser();
                return { success: true };
            } else {
                return { success: false, error: data.detail || 'Login failed' };
            }
        } catch (error) {
            return { success: false, error: 'Network error' };
        }
    },

    // Register
    async register(userData) {
        try {
            const response = await API.auth.register(userData);
            const data = await response.json();

            if (response.ok) {
                // Auto login after registration
                return await this.login(userData.email, userData.password);
            } else {
                return { success: false, error: data };
            }
        } catch (error) {
            return { success: false, error: 'Network error' };
        }
    },

    // Load user profile
    async loadUser() {
        try {
            const response = await API.auth.getProfile();
            if (response.ok) {
                this.user = await response.json();
                return this.user;
            }
        } catch (error) {
            console.error('Failed to load user:', error);
        }
        return null;
    },

    // Logout
    logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        this.user = null;
        WebSocketService.disconnect();
        App.showAuth();
    },

    // Get current user
    getUser() {
        return this.user;
    }
};