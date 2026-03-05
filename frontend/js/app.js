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
        'insights': { title: 'Insights', icon: 'fa-chart-bar', component: () => InsightDashboard },
        'reports': { title: 'Reports', icon: 'fa-file-alt', component: () => ReportPanel }
    },
    activeComponent: null,

    init() {
        this.bindAuthForms();
        API._initSessionTimer();

        // Check for Google OAuth callback token in URL
        const urlParams = new URLSearchParams(window.location.search);
        const googleToken = urlParams.get('google_token');
        const authError = urlParams.get('auth_error');

        // Clean up URL params
        if (googleToken || authError) {
            window.history.replaceState({}, '', '/app');
        }

        if (authError) {
            this.showLogin();
            const errEl = document.getElementById('login-error');
            if (errEl) {
                const errorMessages = {
                    'token_exchange_failed': 'Google sign-in failed. Please try again.',
                    'no_id_token': 'Google did not return authentication info.',
                    'invalid_token': 'Invalid Google authentication response.',
                    'no_email': 'Could not get email from Google account.',
                    'account_deactivated': 'This account has been deactivated.',
                    'no_code': 'Google sign-in was cancelled.',
                };
                errEl.textContent = errorMessages[authError] || `Google sign-in error: ${authError}`;
                errEl.hidden = false;
            }
            return;
        }

        if (googleToken) {
            API.setToken(googleToken);
            this.validateToken();
            return;
        }

        // Check if user is already logged in
        const token = API.getToken();
        if (token) {
            this.validateToken();
        } else {
            this.showLogin();
        }
    },

    /* ── Authentication ────────────────────────── */
    googleLogin() {
        // Redirect to backend Google OAuth endpoint
        window.location.href = '/api/auth/google/login';
    },

    showLogin() {
        document.getElementById('login-overlay')?.classList.remove('hidden');
    },

    hideLogin() {
        document.getElementById('login-overlay')?.classList.add('hidden');
    },

    bindAuthForms() {
        // Google Sign-In button (outside forms — always visible)
        document.getElementById('google-login-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.googleLogin();
        });
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
            const roleName = { founder: 'Founder', pm: 'Product Manager', designer: 'Designer', engineer: 'Engineer', respondent: 'Respondent', executive: 'Executive', other: this.customRoleLabel || 'Other' };
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
        if (this.viewMode === 'story') {
            this.renderDashboardStory();
            return;
        }
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
                    const trendCanvas = document.getElementById('dash-chart-trend');
                    if (trendCanvas) trendCanvas.parentElement.innerHTML = '<div class="empty-state"><p>No sentiment trend data yet.</p></div>';
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

    /* ── Dashboard Story Mode ──────────────────────────── */
    async renderDashboardStory() {
        const page = document.getElementById('page-dashboard');
        if (!page) return;

        page.innerHTML = `
            <div class="story-view">
                <div class="story-loading">
                    <div class="story-loading-icon"><i class="fas fa-book-reader fa-3x fa-pulse"></i></div>
                    <p class="story-loading-text">Building your research story...</p>
                    <div class="story-loading-bar"><div class="story-loading-progress"></div></div>
                </div>
            </div>
        `;

        try {
            const [surveys, notifications] = await Promise.all([
                API.surveys.list().catch(() => []),
                API.notifications.list().catch(() => [])
            ]);

            if (surveys.length === 0) {
                page.innerHTML = `
                    <div class="story-view">
                        <div class="story-section">
                            <div class="story-empty">
                                <i class="fas fa-book-open" style="font-size:3rem;color:var(--neutral-300);margin-bottom:var(--space-3)"></i>
                                <h3>Your Research Story Begins Here</h3>
                                <p class="text-muted">Create your first survey and collect responses to generate a compelling research narrative.</p>
                                <button class="btn btn-primary mt-3" onclick="window.location.hash='survey-designer'">
                                    <i class="fas fa-magic"></i> Create First Survey
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                return;
            }

            // Pick the most recent survey for the story
            const sorted = [...surveys].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
            this.activeSurveyId = sorted[0].id;

            // Fetch story for the active survey
            let story;
            try {
                story = await API.insights.getStory(this.activeSurveyId);
            } catch {
                // Build local fallback
                const summary = await API.insights.getSummary(this.activeSurveyId).catch(() => ({}));
                story = {
                    headline: `Research Overview: ${surveys.length} Active Surveys`,
                    executive_summary: `You have ${surveys.length} survey${surveys.length > 1 ? 's' : ''} collecting feedback. ${summary.total_responses || 0} responses have been gathered so far with ${summary.total_insights || 0} insights discovered.`,
                    sentiment_narrative: 'Switch to the Insights page and select a survey to see detailed sentiment analysis.',
                    theme_narrative: `${summary.total_themes || 0} themes have been identified across your research.`,
                    key_findings: (summary.top_insights || []).slice(0, 3).map(i => ({
                        title: i.title || 'Insight',
                        description: i.description || ''
                    })),
                    highlight_quote: surveys.length > 0 ? `Your most recent survey "${sorted[0].title || 'Untitled'}" is actively collecting feedback.` : '',
                    recommendations_narrative: 'Continue collecting responses to strengthen your insights. The more data you gather, the more accurate the analysis becomes.',
                    outlook: 'Your research infrastructure is set up and ready. Each new response will deepen the understanding of your users.',
                    stats: {
                        total_responses: summary.total_responses || 0,
                        total_themes: summary.total_themes || 0,
                        total_insights: summary.total_insights || 0,
                        total_recommendations: summary.feature_areas?.length || 0,
                        sentiment_distribution: {}
                    },
                    themes: [],
                    survey_title: sorted[0].title || 'Survey'
                };
                (summary.sentiment_distribution || []).forEach(s => {
                    story.stats.sentiment_distribution[s.sentiment] = s.count;
                });
            }

            // Add survey overview to the story
            const surveyListHTML = surveys.length > 0 ? `
                <div class="story-section">
                    <h2 class="story-subtitle"><i class="fas fa-folder-open"></i> Your Surveys</h2>
                    <div class="story-survey-list">
                        ${sorted.slice(0, 5).map(s => `
                            <div class="story-survey-item" onclick="window.location.hash='insights'; App.activeSurveyId=${s.id};">
                                <div class="story-survey-title">${Helpers.escapeHtml(s.title || 'Untitled Survey')}</div>
                                <div class="story-survey-meta">${Helpers.timeAgo(s.created_at)} · ${s.status || 'active'}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : '';

            // Render using same story template as InsightDashboard
            const stats = story.stats || {};
            const sentDist = stats.sentiment_distribution || {};
            const themes = story.themes || [];
            const findings = story.key_findings || [];
            const pos = sentDist.positive || 0;
            const neu = sentDist.neutral || 0;
            const neg = sentDist.negative || 0;
            const total = pos + neu + neg || 1;

            page.innerHTML = `
                <div class="story-view stagger-children">
                    <div class="story-section story-header-section">
                        <div class="story-eyebrow"><i class="fas fa-book-open"></i> Research Story</div>
                        <h1 class="story-title">${Helpers.escapeHtml(story.headline || 'Your Research Overview')}</h1>
                        <p class="story-text story-lead">${Helpers.escapeHtml(story.executive_summary || '')}</p>
                    </div>

                    <div class="story-section">
                        <h2 class="story-subtitle"><i class="fas fa-chart-bar"></i> At a Glance</h2>
                        <div class="story-stat-row">
                            <div class="story-stat">
                                <div class="story-stat-value">${surveys.length}</div>
                                <div class="story-stat-label">Surveys</div>
                            </div>
                            <div class="story-stat">
                                <div class="story-stat-value">${Helpers.formatNumber(stats.total_responses || 0)}</div>
                                <div class="story-stat-label">Responses</div>
                            </div>
                            <div class="story-stat">
                                <div class="story-stat-value">${stats.total_insights || 0}</div>
                                <div class="story-stat-label">Insights</div>
                            </div>
                            <div class="story-stat">
                                <div class="story-stat-value">${stats.total_themes || 0}</div>
                                <div class="story-stat-label">Themes</div>
                            </div>
                        </div>
                    </div>

                    ${(pos + neu + neg) > 0 ? `
                    <div class="story-section">
                        <h2 class="story-subtitle"><i class="fas fa-heart"></i> Sentiment</h2>
                        <p class="story-text">${Helpers.escapeHtml(story.sentiment_narrative || '')}</p>
                        <div class="story-sentiment-bar">
                            <div class="story-sent-segment story-sent-positive" style="width:${Math.round(pos/total*100)}%"><span>${Math.round(pos/total*100)}%</span></div>
                            <div class="story-sent-segment story-sent-neutral" style="width:${Math.round(neu/total*100)}%"><span>${Math.round(neu/total*100)}%</span></div>
                            <div class="story-sent-segment story-sent-negative" style="width:${Math.round(neg/total*100)}%"><span>${Math.round(neg/total*100)}%</span></div>
                        </div>
                        <div class="story-sentiment-legend">
                            <span><span class="story-legend-dot" style="background:var(--success)"></span> Positive</span>
                            <span><span class="story-legend-dot" style="background:var(--warning)"></span> Neutral</span>
                            <span><span class="story-legend-dot" style="background:var(--danger)"></span> Negative</span>
                        </div>
                    </div>
                    ` : ''}

                    ${story.highlight_quote ? `
                    <div class="story-section">
                        <div class="story-highlight">
                            <i class="fas fa-quote-left" style="color:var(--warning);margin-right:var(--space-2)"></i>
                            ${Helpers.escapeHtml(story.highlight_quote)}
                        </div>
                    </div>
                    ` : ''}

                    ${findings.length > 0 ? `
                    <div class="story-section">
                        <h2 class="story-subtitle"><i class="fas fa-lightbulb"></i> Key Findings</h2>
                        <div class="story-findings">
                            ${findings.map((f, i) => `
                                <div class="story-finding">
                                    <div class="story-finding-number">${i + 1}</div>
                                    <div class="story-finding-body">
                                        <div class="story-finding-title">${Helpers.escapeHtml(f.title || '')}</div>
                                        <div class="story-finding-desc">${Helpers.escapeHtml(f.description || '')}</div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    ` : ''}

                    ${surveyListHTML}

                    ${story.outlook ? `
                    <div class="story-section story-outlook">
                        <div class="story-outlook-card">
                            <i class="fas fa-binoculars"></i>
                            <p>${Helpers.escapeHtml(story.outlook)}</p>
                        </div>
                    </div>
                    ` : ''}
                </div>
            `;
        } catch (e) {
            console.error('Dashboard story error:', e);
            page.innerHTML = `
                <div class="story-view">
                    <div class="story-section">
                        <div class="story-empty">
                            <i class="fas fa-exclamation-circle" style="font-size:2rem;color:var(--warning);margin-bottom:var(--space-3)"></i>
                            <h3>Could Not Load Story</h3>
                            <p class="text-muted">An error occurred loading the narrative view. Try switching back to Explore.</p>
                        </div>
                    </div>
                </div>
            `;
        }
    },

    /* ── Role Selector ─────────────────────────────────── */
    bindRoleSelector() {
        const roleSelect = document.getElementById('role-select');
        const customInput = document.getElementById('role-custom-input');
        if (roleSelect) {
            roleSelect.addEventListener('change', () => {
                if (roleSelect.value === 'other') {
                    // Show custom input
                    customInput.hidden = false;
                    customInput.focus();
                } else {
                    customInput.hidden = true;
                    this.currentRole = roleSelect.value;
                    document.body.setAttribute('data-role', this.currentRole);
                    const label = roleSelect.options[roleSelect.selectedIndex].text;
                    Helpers.toast('Role Changed', `Viewing as ${label}`, 'info', 2000);
                }
            });
        }
        if (customInput) {
            const applyCustomRole = () => {
                const val = customInput.value.trim();
                if (val) {
                    this.currentRole = 'other';
                    this.customRoleLabel = val;
                    document.body.setAttribute('data-role', 'other');
                    // Update the "Other..." option text to show the custom role
                    const otherOpt = roleSelect.querySelector('option[value="other"]');
                    if (otherOpt) otherOpt.textContent = val;
                    Helpers.toast('Role Changed', `Viewing as ${val}`, 'info', 2000);
                    customInput.hidden = true;
                }
            };
            customInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); applyCustomRole(); }
                if (e.key === 'Escape') {
                    customInput.hidden = true;
                    roleSelect.value = this.currentRole !== 'other' ? this.currentRole : 'pm';
                }
            });
            customInput.addEventListener('blur', () => {
                if (customInput.value.trim()) applyCustomRole();
                else {
                    customInput.hidden = true;
                    roleSelect.value = this.currentRole !== 'other' ? this.currentRole : 'pm';
                }
            });
        }
    },

    /* ── View Toggle (Explore / Story) ─────────────────── */
    bindViewToggle() {
        document.querySelectorAll('.view-toggle .view-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.dataset.view === this.viewMode) return;
                document.querySelectorAll('.view-toggle .view-btn').forEach(b => {
                    b.classList.remove('active');
                    b.setAttribute('aria-pressed', 'false');
                });
                btn.classList.add('active');
                btn.setAttribute('aria-pressed', 'true');
                this.viewMode = btn.dataset.view;
                document.body.setAttribute('data-view', this.viewMode);

                // Re-render active component or dashboard in the new view mode
                if (this.activeComponent && typeof this.activeComponent.onViewModeChange === 'function') {
                    this.activeComponent.onViewModeChange(this.viewMode);
                } else if (this.currentPage === 'dashboard') {
                    this.renderDashboard();
                }
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
