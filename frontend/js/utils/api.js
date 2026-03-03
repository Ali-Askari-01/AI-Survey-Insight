/**
 * API Client — Handles all HTTP communication with FastAPI backend
 * Includes authentication, error handling, loading states, and response parsing.
 */
const API = {
    BASE_URL: '',  // Same origin
    _token: localStorage.getItem('auth_token') || null,

    // Start session timer for existing token on load
    _initSessionTimer() {
        if (this._token) this._startSessionTimer(this._token);
    },

    setToken(token) {
        this._token = token;
        if (token) {
            localStorage.setItem('auth_token', token);
            this._startSessionTimer(token);
        } else {
            localStorage.removeItem('auth_token');
            this._clearSessionTimer();
        }
    },

    getToken() {
        return this._token;
    },

    // ── Session Timeout ──
    _sessionTimer: null,
    _warningTimer: null,

    _decodeJwtExp(token) {
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.exp ? payload.exp * 1000 : null; // convert to ms
        } catch { return null; }
    },

    _startSessionTimer(token) {
        this._clearSessionTimer();
        const expMs = this._decodeJwtExp(token);
        if (!expMs) return;

        const now = Date.now();
        const remaining = expMs - now;
        if (remaining <= 0) {
            this._handleSessionExpired();
            return;
        }

        // Warn 2 minutes before expiry
        const warnAt = remaining - 120000;
        if (warnAt > 0) {
            this._warningTimer = setTimeout(() => {
                if (typeof Helpers !== 'undefined' && Helpers.toast) {
                    Helpers.toast('Session Expiring', 'Your session will expire in 2 minutes. Save your work.', 'warning', 10000);
                }
            }, warnAt);
        }

        // Expire
        this._sessionTimer = setTimeout(() => {
            this._handleSessionExpired();
        }, remaining);
    },

    _clearSessionTimer() {
        if (this._sessionTimer) { clearTimeout(this._sessionTimer); this._sessionTimer = null; }
        if (this._warningTimer) { clearTimeout(this._warningTimer); this._warningTimer = null; }
    },

    _handleSessionExpired() {
        this._clearSessionTimer();
        this.setToken(null);
        if (typeof Helpers !== 'undefined' && Helpers.toast) {
            Helpers.toast('Session Expired', 'Your session has expired. Please sign in again.', 'warning', 6000);
        }
        if (typeof App !== 'undefined' && App.showLogin) App.showLogin();
    },

    async request(method, endpoint, data = null) {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        // Attach auth token if available
        if (this._token) {
            options.headers['Authorization'] = `Bearer ${this._token}`;
        }
        if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(`${this.BASE_URL}${endpoint}`, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                if (response.status === 401) {
                    // Token expired or invalid — trigger logout with message
                    this._handleSessionExpired();
                }
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`API Error [${method} ${endpoint}]:`, error);
            throw error;
        }
    },

    get(endpoint) { return this.request('GET', endpoint); },
    post(endpoint, data) { return this.request('POST', endpoint, data); },
    put(endpoint, data) { return this.request('PUT', endpoint, data); },
    delete(endpoint) { return this.request('DELETE', endpoint); },

    // ── Authentication ──
    auth: {
        register(name, email, password) {
            return API.post('/api/auth/register', { name, email, password });
        },
        login(email, password) {
            return API.post('/api/auth/login', { email, password });
        },
        me() { return API.get('/api/auth/me'); },
        listUsers() { return API.get('/api/auth/users'); },
        updateRole(userId, role) { return API.put(`/api/auth/users/${userId}/role`, { role }); },
    },

    // ── Feature 1: Survey Designer ──
    surveys: {
        list() { return API.get('/api/surveys/'); },
        get(id) { return API.get(`/api/surveys/${id}`); },
        create(data) { return API.post('/api/surveys/', data); },
        getFlow(id) { return API.get(`/api/surveys/${id}/flow`); },
        getQuestions(id) { return API.get(`/api/surveys/${id}`).then(s => s.questions || []); },

        // Questions
        createQuestion(data) { return API.post('/api/surveys/questions', data); },
        updateQuestion(id, data) { return API.put(`/api/surveys/questions/${id}`, data); },
        deleteQuestion(id) { return API.delete(`/api/surveys/questions/${id}`); },
        reorderQuestions(orders) { return API.post('/api/surveys/questions/reorder', { orders }); },

        // AI
        parseGoal(input) { return API.post('/api/surveys/goals/ai-parse', { user_input: input }); },
        generateQuestions(goalId, count) { return API.post('/api/surveys/questions/ai-generate', { research_goal_id: goalId, count }); },
        generateDeepQuestions(goalText, researchType, count) {
            return API.post('/api/surveys/questions/ai-generate-deep', { goal_text: goalText, research_type: researchType, count });
        },
        intakeClarify(message, conversation) {
            return API.post('/api/surveys/intake/clarify', { message, conversation });
        },
        generateAudienceTargeted(goalText, targetAudiences, researchType, countPerAudience) {
            return API.post('/api/surveys/questions/ai-generate-audience-targeted', {
                goal_text: goalText, target_audiences: targetAudiences,
                research_type: researchType, count_per_audience: countPerAudience
            });
        },
        generateConsent(title, goal) { return API.post('/api/surveys/generate-consent', { title, goal }); },

        // Templates
        getTemplates() { return API.get('/api/surveys/templates'); },

        // Goals
        listGoals() { return API.get('/api/surveys/goals'); },
        getGoal(id) { return API.get(`/api/surveys/goals/${id}`); },
        createGoal(data) { return API.post('/api/surveys/goals', data); },
    },

    // ── Feature 2 & 5: Interviews ──
    interviews: {
        createSession(data) { return API.post('/api/interviews/sessions', data); },
        getSession(id) { return API.get(`/api/interviews/sessions/${id}`); },
        resumeSession(id) { return API.post(`/api/interviews/sessions/${id}/resume`); },
        respond(data) { return API.post('/api/interviews/respond', data); },
        chat(data) { return API.post('/api/interviews/chat', data); },
        getHistory(sessionId) { return API.get(`/api/interviews/sessions/${sessionId}/history`); },
        completeInterview(sessionId) { return API.post(`/api/interviews/sessions/${sessionId}/complete`); },
        getMetrics(surveyId) { return API.get(`/api/interviews/metrics/${surveyId}`); },

        // Voice transcription (AssemblyAI)
        async transcribe(audioBlob, filename = 'recording.webm') {
            const formData = new FormData();
            formData.append('file', audioBlob, filename);
            const resp = await fetch('/api/interviews/transcribe', { method: 'POST', body: formData });
            if (!resp.ok) throw new Error(`Transcription failed: ${resp.status}`);
            return resp.json();
        },
        async transcribeAndRespond(audioBlob, sessionId, questionId, filename = 'recording.webm') {
            const formData = new FormData();
            formData.append('file', audioBlob, filename);
            const url = `/api/interviews/transcribe-and-respond?session_id=${encodeURIComponent(sessionId)}&question_id=${questionId}`;
            const resp = await fetch(url, { method: 'POST', body: formData });
            if (!resp.ok) throw new Error(`Transcribe & respond failed: ${resp.status}`);
            return resp.json();
        },
    },

    // ── Feature 3: Insights ──
    insights: {
        get(surveyId, filters = {}) {
            const params = new URLSearchParams();
            Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
            const qs = params.toString();
            return API.get(`/api/insights/${surveyId}${qs ? '?' + qs : ''}`);
        },
        getSummary(surveyId) { return API.get(`/api/insights/${surveyId}/summary`); },
        getThemes(surveyId) { return API.get(`/api/insights/themes/${surveyId}`); },
        getBubbleData(surveyId) { return API.get(`/api/insights/themes/${surveyId}/bubble-data`); },
        getBubbles(surveyId) { return API.get(`/api/insights/themes/${surveyId}/bubble-data`); },
        getSentiment(surveyId) { return API.get(`/api/insights/sentiment/${surveyId}`); },
        getHeatmap(surveyId) { return API.get(`/api/insights/sentiment/${surveyId}/heatmap`); },
        getTrends(surveyId) { return API.get(`/api/insights/sentiment/${surveyId}/trends`); },
        getPatterns(surveyId) { return API.get(`/api/insights/patterns/${surveyId}`); },
    },

    // ── Feature 4: Reports ──
    reports: {
        getSummary(surveyId, tone = 'neutral', length = 'medium') {
            return API.get(`/api/reports/summary/${surveyId}?tone=${tone}&length=${length}`);
        },
        generate(data) { return API.post('/api/reports/generate', data); },
        list(surveyId) { return API.get(`/api/reports/${surveyId}`); },
        getRecommendations(surveyId, filters = {}) {
            const params = new URLSearchParams();
            Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
            const qs = params.toString();
            return API.get(`/api/reports/recommendations/${surveyId}${qs ? '?' + qs : ''}`);
        },
        getMatrix(surveyId) { return API.get(`/api/reports/recommendations/${surveyId}/matrix`); },
        getRoadmap(surveyId) { return API.get(`/api/reports/recommendations/${surveyId}/roadmap`); },
        exportCSV(surveyId) { return API.get(`/api/reports/export/${surveyId}/csv`); },
        exportJira(surveyId) { return API.get(`/api/reports/export/${surveyId}/jira`); },
    },

    // ── Feature 5: Notifications ──
    notifications: {
        list(filters = {}) {
            const params = new URLSearchParams();
            Object.entries(filters).forEach(([k, v]) => { if (v !== undefined) params.append(k, v); });
            const qs = params.toString();
            return API.get(`/api/notifications/${qs ? '?' + qs : ''}`);
        },
        getUnreadCount() { return API.get('/api/notifications/unread-count'); },
        markRead(id) { return API.put(`/api/notifications/${id}/read`); },
        markAllRead() { return API.put('/api/notifications/read-all'); },
        create(data) { return API.post('/api/notifications/', data); },
        delete(id) { return API.delete(`/api/notifications/${id}`); },
        emailStatus() { return API.get('/api/notifications/email-status'); },
        sendInvites(surveyId, emails) { return API.post('/api/notifications/send-invites', { survey_id: surveyId, emails }); },
    },

    // ── Simulation ──
    simulation: {
        run(surveyId, persona = null, count = 1) {
            return API.post('/api/interviews/simulate', { survey_id: surveyId, persona, num_simulations: count });
        }
    },

    // ── Survey Publishing & Respondent Management ──
    publish: {
        publish(data) { return API.post('/api/publish/', data); },
        mySurveys() { return API.get('/api/publish/my-surveys'); },
        getSurveyByCode(code) { return API.get(`/api/publish/s/${code}`); },
        join(data) { return API.post('/api/publish/join', data); },
        analytics(surveyId) { return API.get(`/api/publish/analytics/${surveyId}`); },
        analysis(surveyId) { return API.get(`/api/publish/analysis/${surveyId}`); },
        updateStatus(shareCode, status) { return API.put(`/api/publish/${shareCode}/status`, { status }); },
        saveTranscript(sessionId) { return API.post(`/api/publish/transcripts/${sessionId}`); },
        getTranscripts(surveyId) { return API.get(`/api/publish/transcripts/${surveyId}/all`); },
        getSessionTranscript(sessionId) { return API.get(`/api/publish/transcripts/session/${sessionId}`); },
        exportRespondentsCSV(surveyId) { return API._downloadFile(`/api/publish/export/${surveyId}/respondents-csv`); },
        exportAnalysisCSV(surveyId) { return API._downloadFile(`/api/publish/export/${surveyId}/analysis-csv`); },
        exportReportHTML(surveyId) { return API._downloadFile(`/api/publish/export/${surveyId}/report-html`); },
    },

    // ── File Download Helper ──
    async _downloadFile(endpoint) {
        const headers = {};
        const token = localStorage.getItem('auth_token');
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const resp = await fetch(endpoint, { headers });
        if (resp.status === 401) {
            this._handleSessionExpired();
            throw new Error('Session expired. Please sign in again.');
        }
        if (!resp.ok) throw new Error(`Download failed: ${resp.status}`);
        const blob = await resp.blob();
        const disposition = resp.headers.get('Content-Disposition') || '';
        const match = disposition.match(/filename=(.+)/);
        const filename = match ? match[1] : 'download';
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename;
        document.body.appendChild(a); a.click();
        document.body.removeChild(a); URL.revokeObjectURL(url);
    },

    // ── WebSocket ──
    ws: {
        _socket: null,
        _listeners: [],
        _reconnectDelay: 5000,
        _maxReconnectDelay: 60000,

        connect() {
            // Don't create duplicate connections
            if (this._socket && (this._socket.readyState === WebSocket.OPEN || this._socket.readyState === WebSocket.CONNECTING)) {
                return;
            }
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            this._socket = new WebSocket(`${protocol}//${window.location.host}/ws/dashboard`);
            this._socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this._listeners.forEach(fn => fn(data));
                } catch (e) {
                    console.warn('WebSocket parse error:', e);
                }
            };
            this._socket.onclose = () => {
                // Reconnect with exponential backoff
                setTimeout(() => this.connect(), this._reconnectDelay);
                this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxReconnectDelay);
            };
            this._socket.onopen = () => {
                this._reconnectDelay = 5000; // Reset on successful connect
            };
            this._socket.onerror = (e) => {
                console.warn('WebSocket error:', e);
            };
        },

        onMessage(callback) {
            this._listeners.push(callback);
        },

        removeListener(callback) {
            this._listeners = this._listeners.filter(fn => fn !== callback);
        },

        send(data) {
            if (this._socket && this._socket.readyState === WebSocket.OPEN) {
                this._socket.send(JSON.stringify(data));
            }
        }
    },
};
