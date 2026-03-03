/**
 * App.js — Main SPA Controller & Router
 * Handles: authentication, page routing, sidebar nav, role switching, view toggle, WebSocket
 */
const App = {
    currentPage: 'dashboard',
    currentRole: 'pm',
    currentUser: null,
    viewMode: 'explore',
    activeSurveyId: null,  // Tracks the currently selected survey for insights/reports
    pages: {
        dashboard: { title: 'Dashboard', icon: 'fa-th-large', component: null },
        'survey-designer': { title: 'Survey Designer', icon: 'fa-magic', component: () => SurveyDesigner },
        'my-surveys': { title: 'My Surveys', icon: 'fa-folder-open', component: () => MySurveys },
        'web-form': { title: 'Web Form', icon: 'fa-clipboard-list', component: () => WebForm },
        'chat': { title: 'Chat Interview', icon: 'fa-comments', component: () => ChatInterface },
        'voice': { title: 'Voice Input', icon: 'fa-microphone', component: () => VoiceInput },
        'insights': { title: 'Insights', icon: 'fa-chart-bar', component: () => InsightDashboard },
        'reports': { title: 'Reports', icon: 'fa-file-alt', component: () => ReportPanel }
    },
    activeComponent: null,

    init() {
        this.bindAuthForms();
        API._initSessionTimer();

        // Check if user is already logged in
        const token = API.getToken();
        if (token) {
            this.validateToken();
        } else {
            this.showLogin();
        }
    },

    /* ── Authentication ────────────────────────── */
    showLogin() {
        document.getElementById('login-overlay')?.classList.remove('hidden');
    },

    hideLogin() {
        document.getElementById('login-overlay')?.classList.add('hidden');
    },

    bindAuthForms() {
        // Toggle between login/register
        document.getElementById('show-register')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('login-form').hidden = true;
            document.getElementById('register-form').hidden = false;
        });
        document.getElementById('show-login')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('login-form').hidden = false;
            document.getElementById('register-form').hidden = true;
        });

        // Login form
        document.getElementById('login-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            const errEl = document.getElementById('login-error');
            const btn = document.getElementById('login-btn');
            try {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';
                errEl.hidden = true;
                const result = await API.auth.login(email, password);
                API.setToken(result.access_token);
                this.currentUser = result.user;
                this.onLoginSuccess();
            } catch (err) {
                errEl.textContent = err.message || 'Login failed';
                errEl.hidden = false;
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Sign In';
            }
        });

        // Register form
        document.getElementById('register-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('reg-name').value;
            const email = document.getElementById('reg-email').value;
            const password = document.getElementById('reg-password').value;
            const errEl = document.getElementById('register-error');
            const btn = document.getElementById('register-btn');

            // Client-side password validation
            if (password.length < 8) {
                errEl.textContent = 'Password must be at least 8 characters';
                errEl.hidden = false;
                return;
            }
            if (!/[A-Z]/.test(password)) {
                errEl.textContent = 'Password must contain at least one uppercase letter';
                errEl.hidden = false;
                return;
            }
            if (!/[a-z]/.test(password)) {
                errEl.textContent = 'Password must contain at least one lowercase letter';
                errEl.hidden = false;
                return;
            }
            if (!/[0-9]/.test(password)) {
                errEl.textContent = 'Password must contain at least one number';
                errEl.hidden = false;
                return;
            }

            try {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
                errEl.hidden = true;
                const result = await API.auth.register(name, email, password);
                API.setToken(result.access_token);
                this.currentUser = result.user;
                this.onLoginSuccess();
            } catch (err) {
                errEl.textContent = err.message || 'Registration failed';
                errEl.hidden = false;
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
            }
        });
    },

    async validateToken() {
        // Show a subtle loading state while validating
        const overlay = document.getElementById('login-overlay');
        if (overlay && !overlay.classList.contains('hidden')) {
            // Login overlay is already showing, no need for extra loading
        } else {
            Helpers.showLoading('page', 'Validating session...');
        }
        try {
            const user = await API.auth.me();
            this.currentUser = user;
            this.onLoginSuccess();
        } catch {
            API.setToken(null);
            this.showLogin();
        } finally {
            Helpers.hideLoading('page');
        }
    },

    onLoginSuccess() {
        this.hideLogin();
        this.currentRole = this.currentUser?.role || 'pm';
        this.updateUserUI();
        this.initApp();
    },

    logout() {
        API._clearSessionTimer();
        API.setToken(null);
        this.currentUser = null;
        this.showLogin();
        // Reset forms
        document.getElementById('login-form')?.reset();
        document.getElementById('register-form')?.reset();
        document.getElementById('login-form').hidden = false;
        document.getElementById('register-form').hidden = true;
    },

    updateUserUI() {
        // Update sidebar footer with user info
        const footer = document.querySelector('.sidebar-footer');
        if (footer && this.currentUser) {
            const initials = this.currentUser.name ? this.currentUser.name.split(' ').map(n => n[0]).join('').toUpperCase() : '?';
            const roleName = { founder: 'Founder', pm: 'Product Manager', designer: 'Designer', engineer: 'Engineer', respondent: 'Respondent' };
            const userInfoHTML = `
                <div class="user-info">
                    <div class="user-avatar">${initials}</div>
                    <div class="user-details">
                        <div class="user-name">${Helpers.escapeHtml(this.currentUser.name)}</div>
                        <div class="user-role">${roleName[this.currentUser.role] || this.currentUser.role}</div>
                    </div>
                    <button class="btn-logout" onclick="App.logout()" title="Sign out"><i class="fas fa-sign-out-alt"></i></button>
                </div>
            `;
            // Insert before role selector or replace existing
            const existing = footer.querySelector('.user-info');
            if (existing) {
                existing.outerHTML = userInfoHTML;
            } else {
                footer.insertAdjacentHTML('afterbegin', userInfoHTML);
            }
        }

        // Set role selector to match user role
        const roleSelect = document.getElementById('role-select');
        if (roleSelect && this.currentUser) {
            roleSelect.value = this.currentUser.role;
            document.body.setAttribute('data-role', this.currentUser.role);
        }
    },

    /* ── Initialize App (after login) ─────────── */
    initApp() {
        this.bindNavigation();
        this.bindRoleSelector();
        this.bindViewToggle();
        this.bindSearch();
        this.bindSidebarToggle();

        // Initialize notifications
        NotificationsComponent.init();

        // Connect WebSocket for live updates
        try { API.ws.connect(); } catch (e) { console.warn('WebSocket unavailable:', e); }

        // Bind modal close button
        document.getElementById('modal-close')?.addEventListener('click', () => Helpers.closeModal());
        document.getElementById('modal-overlay')?.addEventListener('click', (e) => {
            if (e.target === e.currentTarget) Helpers.closeModal();
        });

        // Route from hash or default
        const hash = window.location.hash.replace('#', '') || 'dashboard';
        this.navigate(hash);

        // Listen for hash changes
        window.addEventListener('hashchange', () => {
            const page = window.location.hash.replace('#', '') || 'dashboard';
            this.navigate(page);
        });

        console.log('🚀 AI Survey Software initialized');
    },

    /* ── Navigation ─────────────────────────────────────── */
    bindNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                if (page) {
                    window.location.hash = page;
                }
            });
        });
    },

    navigate(page) {
        if (!this.pages[page]) page = 'dashboard';

        // Destroy previous component
        if (this.activeComponent && typeof this.activeComponent.destroy === 'function') {
            this.activeComponent.destroy();
        }

        this.currentPage = page;

        // Update sidebar active state
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });

        // Update page title
        const topTitle = document.getElementById('page-title');
        if (topTitle) topTitle.textContent = this.pages[page].title;

        // Hide all pages, show current
        document.querySelectorAll('.page-content').forEach(el => el.classList.remove('active'));
        const pageEl = document.getElementById('page-' + page);
        if (pageEl) pageEl.classList.add('active');

        // Initialize component
        const pageConfig = this.pages[page];
        if (pageConfig.component) {
            this.activeComponent = pageConfig.component();
            if (this.activeComponent && typeof this.activeComponent.init === 'function') {
                this.activeComponent.init();
            }
        } else if (page === 'dashboard') {
            this.activeComponent = null;
            this.renderDashboard();
        }
    },

    /* ── Dashboard (landing page) ──────────────────────── */
    async renderDashboard() {
        const page = document.getElementById('page-dashboard');
        if (!page) return;

        page.innerHTML = `
            <div class="dashboard stagger-children">
                <!-- Welcome Banner -->
                <div class="card mb-3" style="background: linear-gradient(135deg, var(--primary-500), var(--primary-700)); color: white; padding: var(--space-4)">
                    <h2 style="margin:0">Welcome to AI Survey Insights</h2>
                    <p style="opacity:0.9;margin-top:var(--space-1)">Your multi-channel feedback engine is ready. Here's an overview of your research.</p>
                </div>

                <!-- Quick Stats -->
                <div class="grid grid-4 gap-2 mb-3" id="dash-stats">
                    <div class="card stat-card">
                        <div class="stat-icon" style="background:var(--primary-100);color:var(--primary-600)"><i class="fas fa-poll"></i></div>
                        <div class="stat-content"><div class="stat-value" id="dash-surveys">${Helpers.skeleton(1, 'stat')}</div><div class="stat-label">Active Surveys</div></div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-icon" style="background:#dcfce7;color:var(--success)"><i class="fas fa-comments"></i></div>
                        <div class="stat-content"><div class="stat-value" id="dash-responses">${Helpers.skeleton(1, 'stat')}</div><div class="stat-label">Total Responses</div></div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-icon" style="background:#fef3c7;color:var(--warning)"><i class="fas fa-lightbulb"></i></div>
                        <div class="stat-content"><div class="stat-value" id="dash-insights">${Helpers.skeleton(1, 'stat')}</div><div class="stat-label">Insights</div></div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-icon" style="background:#ede9fe;color:#7c3aed"><i class="fas fa-check-double"></i></div>
                        <div class="stat-content"><div class="stat-value" id="dash-recs">${Helpers.skeleton(1, 'stat')}</div><div class="stat-label">Recommendations</div></div>
                    </div>
                </div>

                <!-- Charts Row -->
                <div class="grid grid-2 gap-2 mb-3">
                    <div class="card dashboard-card">
                        <div class="card-header"><h3><i class="fas fa-chart-line"></i> Sentiment Trend</h3></div>
                        <div class="card-body chart-container"><canvas id="dash-chart-trend"></canvas></div>
                    </div>
                    <div class="card dashboard-card">
                        <div class="card-header"><h3><i class="fas fa-chart-pie"></i> Sentiment Distribution</h3></div>
                        <div class="card-body chart-container"><canvas id="dash-chart-donut"></canvas></div>
                    </div>
                </div>

                <!-- Channel Cards -->
                <h3 class="mb-2"><i class="fas fa-signal"></i> Collection Channels</h3>
                <div class="grid grid-3 gap-2 mb-3">
                    <div class="card channel-card" style="cursor:pointer" onclick="window.location.hash='web-form'">
                        <div class="card-body" style="text-align:center;padding:var(--space-4)">
                            <i class="fas fa-clipboard-list" style="font-size:2rem;color:var(--primary-500)"></i>
                            <h4 class="mt-2">Web Form</h4>
                            <p class="text-muted">Progressive, conversational surveys</p>
                        </div>
                    </div>
                    <div class="card channel-card" style="cursor:pointer" onclick="window.location.hash='chat'">
                        <div class="card-body" style="text-align:center;padding:var(--space-4)">
                            <i class="fas fa-comments" style="font-size:2rem;color:var(--success)"></i>
                            <h4 class="mt-2">Chat Interview</h4>
                            <p class="text-muted">WhatsApp-style AI conversations</p>
                        </div>
                    </div>
                    <div class="card channel-card" style="cursor:pointer" onclick="window.location.hash='voice'">
                        <div class="card-body" style="text-align:center;padding:var(--space-4)">
                            <i class="fas fa-microphone" style="font-size:2rem;color:var(--warning)"></i>
                            <h4 class="mt-2">Voice Input</h4>
                            <p class="text-muted">Speak naturally, AI transcribes</p>
                        </div>
                    </div>
                </div>

                <!-- Recent Activity -->
                <div class="card">
                    <div class="card-header"><h3><i class="fas fa-history"></i> Recent Activity</h3></div>
                    <div class="card-body" id="dash-activity"><div class="spinner"></div></div>
                </div>
            </div>
        `;

        // Load dashboard data
        this.loadDashboardData();
    },

    async loadDashboardData() {
        try {
            const [surveys, notifications] = await Promise.all([
                API.surveys.list().catch(() => []),
                API.notifications.list().catch(() => [])
            ]);

            // Set active survey — pick the most recent one (or first available)
            if (surveys.length > 0) {
                const sorted = [...surveys].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
                this.activeSurveyId = sorted[0].id;
            } else {
                this.activeSurveyId = 1; // fallback
            }

            // Load summary for the active survey
            const summary = await API.insights.getSummary(this.activeSurveyId).catch(() => ({}));

            // Stat cards
            document.getElementById('dash-surveys').textContent = surveys.length || 0;
            document.getElementById('dash-responses').textContent = Helpers.formatNumber(summary.total_responses || 0);
            document.getElementById('dash-insights').textContent = summary.total_insights || 0;
            document.getElementById('dash-recs').textContent = summary.feature_areas?.length || 0;

            // Sentiment donut — use actual sentiment_distribution from summary
            const sentDist = summary.sentiment_distribution || [];
            const sentMap = {};
            sentDist.forEach(s => { sentMap[s.sentiment] = s.count; });
            const totalSent = Object.values(sentMap).reduce((a, b) => a + b, 0) || 1;

            Charts.sentimentDoughnut('dash-chart-donut', {
                positive: sentMap.positive || 0,
                neutral: sentMap.neutral || 0,
                negative: sentMap.negative || 0
            });

            // Sentiment trend — use real trend data from API
            try {
                const trends = await API.insights.getTrends(this.activeSurveyId).catch(() => ({}));
                if (trends && Object.keys(trends).length > 0) {
                    Charts.sentimentTrend('dash-chart-trend', trends);
                } else {
                    // Fallback to static placeholder
                    const labels = ['Week 1', 'Week 2', 'Week 3', 'Week 4'];
                    Charts.sentimentTrend('dash-chart-trend', labels, {
                        positive: [60, 62, 65, 68],
                        neutral: [25, 24, 23, 22],
                        negative: [15, 14, 12, 10]
                    });
                }
            } catch { /* trend chart is optional */ }

            // Recent activity from notifications
            const activityContainer = document.getElementById('dash-activity');
            if (activityContainer) {
                if (notifications.length === 0) {
                    activityContainer.innerHTML = '<div class="text-muted">No recent activity.</div>';
                } else {
                    activityContainer.innerHTML = notifications.slice(0, 5).map(n => {
                        const info = Helpers.severityInfo(n.severity);
                        return `
                            <div class="flex gap-2 align-center" style="padding:var(--space-2) 0;border-bottom:1px solid var(--border)">
                                <div style="width:32px;height:32px;border-radius:50%;background:${info.bg};color:${info.color};display:flex;align-items:center;justify-content:center">
                                    <i class="fas ${info.icon}"></i>
                                </div>
                                <div style="flex:1">
                                    <div>${Helpers.escapeHtml(n.title)}</div>
                                    <div class="text-muted" style="font-size:0.8rem">${Helpers.timeAgo(n.created_at)}</div>
                                </div>
                            </div>
                        `;
                    }).join('');
                }
            }
        } catch (e) {
            console.error('Dashboard data load error:', e);
        }
    },

    /* ── Role Selector ─────────────────────────────────── */
    bindRoleSelector() {
        const roleSelect = document.getElementById('role-select');
        if (roleSelect) {
            roleSelect.addEventListener('change', () => {
                this.currentRole = roleSelect.value;
                document.body.setAttribute('data-role', this.currentRole);
                const label = roleSelect.options[roleSelect.selectedIndex].text;
                Helpers.toast('Role Changed', `Viewing as ${label}`, 'info', 2000);
            });
        }
    },

    /* ── View Toggle (Explore / Story) ─────────────────── */
    bindViewToggle() {
        document.querySelectorAll('.view-toggle .view-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.view-toggle .view-btn').forEach(b => {
                    b.classList.remove('active');
                    b.setAttribute('aria-pressed', 'false');
                });
                btn.classList.add('active');
                btn.setAttribute('aria-pressed', 'true');
                this.viewMode = btn.dataset.view;
                document.body.setAttribute('data-view', this.viewMode);
            });
        });
    },

    /* ── Global Search ─────────────────────────────────── */
    bindSearch() {
        const searchInput = document.getElementById('global-search');
        searchInput?.addEventListener('input', Helpers.debounce((e) => {
            const query = e.target.value.trim().toLowerCase();
            if (query.length < 2) return;

            // Simple client-side search across nav items
            const matches = Object.entries(this.pages).filter(([key, cfg]) =>
                cfg.title.toLowerCase().includes(query) || key.includes(query)
            );

            if (matches.length === 1) {
                window.location.hash = matches[0][0];
                searchInput.value = '';
            }
        }, 300));
    },

    /* ── Sidebar Collapse ──────────────────────────────── */
    bindSidebarToggle() {
        const toggleBtn = document.getElementById('sidebar-toggle');
        const sidebar = document.getElementById('sidebar');
        toggleBtn?.addEventListener('click', () => {
            sidebar?.classList.toggle('collapsed');
            document.body.classList.toggle('sidebar-collapsed');
        });

        // Mobile menu button — toggle .mobile-open
        const mobileBtn = document.getElementById('mobile-menu-btn');
        mobileBtn?.addEventListener('click', () => {
            sidebar?.classList.toggle('mobile-open');
            this._toggleMobileOverlay(sidebar?.classList.contains('mobile-open'));
        });

        // Close sidebar when clicking a nav item on mobile
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 1024) {
                    sidebar?.classList.remove('mobile-open');
                    this._toggleMobileOverlay(false);
                }
            });
        });
    },

    _toggleMobileOverlay(show) {
        let overlay = document.getElementById('mobile-sidebar-overlay');
        if (show && !overlay) {
            overlay = document.createElement('div');
            overlay.id = 'mobile-sidebar-overlay';
            overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:99;animation:fadeIn 0.2s ease';
            overlay.addEventListener('click', () => {
                document.getElementById('sidebar')?.classList.remove('mobile-open');
                this._toggleMobileOverlay(false);
            });
            document.body.appendChild(overlay);
        } else if (!show && overlay) {
            overlay.remove();
        }
    }
};

/* ── Bootstrap ──────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
