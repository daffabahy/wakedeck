const API_URL = '/api/v1';

class API {
    static getToken() { return localStorage.getItem('access_token'); }
    static setToken(token) { localStorage.setItem('access_token', token); }
    static clearToken() { localStorage.removeItem('access_token'); }

    static async request(endpoint, options = {}) {
        const token = this.getToken();
        const headers = {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` }),
            ...(options.headers || {})
        };
        
        if (options.body && typeof options.body === 'object') {
            options.body = JSON.stringify(options.body);
        }
        
        const response = await fetch(`${API_URL}${endpoint}`, { ...options, headers });
        
        if (response.status === 401) {
            this.clearToken();
            window.dispatchEvent(new Event('auth-expired'));
            throw new Error('Session expired');
        }
        
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Server error');
        return data;
    }
    
    // Auth
    static checkSetupStatus() { return this.request('/auth/setup-status'); }
    static setupInit(data) { return this.request('/auth/setup', { method: 'POST', body: data }); }
    static async login(username, password) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        const response = await fetch(`${API_URL}/auth/token`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData.toString()
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Invalid credentials');
        this.setToken(data.access_token);
        return data;
    }
    static getMe() { return this.request('/auth/me'); }
    
    // Devices
    static getDevices() { return this.request('/devices/'); }
    static createDevice(data) { return this.request('/devices/', { method: 'POST', body: data }); }
    static updateDevice(id, data) { return this.request(`/devices/${id}`, { method: 'PUT', body: data }); }
    static deleteDevice(id) { return this.request(`/devices/${id}`, { method: 'DELETE' }); }
    
    // Control
    static wakeDevice(id) { return this.request(`/control/${id}/wake`, { method: 'POST' }); }
    static shutdownDevice(id) { return this.request(`/control/${id}/shutdown`, { method: 'POST' }); }
    static restartDevice(id) { return this.request(`/control/${id}/restart`, { method: 'POST' }); }
    static statusDevice(id) { return this.request(`/control/${id}/status`); }
    
    // Network
    static scanNetwork() { return this.request('/network/scan'); }
    
    // History
    static getHistory() { return this.request('/history/'); }
    static clearHistory() { return this.request('/history/', { method: 'DELETE' }); }
    
    // Schedules
    static getSchedules() { return this.request('/schedules/'); }
    static createSchedule(data) { return this.request('/schedules/', { method: 'POST', body: data }); }
    static deleteSchedule(id) { return this.request(`/schedules/${id}`, { method: 'DELETE' }); }
    static getScheduleNextRun(id) { return this.request(`/schedules/${id}/next`); }
    
    // Settings / Notifications
    static getWebhookSettings() { return this.request('/settings/webhook'); }
    static saveWebhookSettings(data) { return this.request('/settings/webhook', { method: 'PUT', body: data }); }
    static clearDiscordWebhook() { return this.request('/settings/webhook/discord', { method: 'DELETE' }); }
    static clearTelegramBot() { return this.request('/settings/webhook/telegram', { method: 'DELETE' }); }
    static testNotification(data) { return this.request('/settings/test-notification', { method: 'POST', body: data }); }
    static getSSHPublicKey() { return this.request('/settings/ssh-public-key'); }
    
    // Timezone
    static getTimezone() { return this.request('/settings/timezone'); }
    static setTimezone(tz) { return this.request('/settings/timezone', { method: 'PUT', body: { timezone: tz } }); }
}
