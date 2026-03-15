/**
 * Analytics Dashboard Component — Founder/Admin Insights
 * ═══════════════════════════════════════════════════════════════
 * Comprehensive analytics dashboard for founders to track:
 * - Website traffic and user behavior
 * - User feedback and satisfaction
 * - Respondent experience insights
 * - Platform performance metrics
 */

class AnalyticsDashboard {
    constructor() {
        this.charts = {};
        this.refreshInterval = null;
        this.currentPeriod = 30;
        this.initialized = false;
    }

    init() {
        if (this.initialized) return;
        
        this.render();
        this.setupEventListeners();
        this.loadDashboard();
        this.setupAutoRefresh();
        this.initialized = true;
    }

    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
        
        // Destroy all charts
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.charts = {};
        this.initialized = false;
    }

    render() {
        const page = document.getElementById('page-analytics');
        if (!page) return;

        page.innerHTML = `
            <div class="analytics-dashboard">
                <!-- Analytics Header -->
                <div class="analytics-header">
                    <div class="header-content">
                        <div class="header-left">
                            <h1 class="header-title">
                                <i class="fas fa-chart-line"></i>
                                Analytics Dashboard
                            </h1>
                            <p class="header-subtitle">Real-time insights into your platform's performance</p>
                        </div>
                        <div class="header-controls">
                            <select class="period-selector" id="analyticsperiodSelector">
                                <option value="7">Last 7 Days</option>
                                <option value="30" selected>Last 30 Days</option>
                                <option value="90">Last 90 Days</option>
                            </select>
                            <button class="refresh-btn" id="analyticsRefreshBtn">
                                <i class="fas fa-sync-alt"></i> Refresh
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Key Metrics Grid -->
                <div class="metrics-grid" id="analyticsMetricsGrid">
                    <!-- Metrics will be populated by JavaScript -->
                </div>

                <!-- Charts Section -->
                <div class="charts-section">
                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">Daily Traffic Trend</h3>
                            <p class="chart-subtitle">Page views and unique visitors over time</p>
                        </div>
                        <canvas id="analyticsTrafficChart" width="400" height="200"></canvas>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">Channel Performance</h3>
                            <p class="chart-subtitle">Survey responses by channel</p>
                        </div>
                        <canvas id="analyticsChannelChart" width="200" height="200"></canvas>
                    </div>
                </div>

                <!-- Feedback Panels -->
                <div class="feedback-panels">
                    <!-- User Feedback -->
                    <div class="feedback-panel">
                        <div class="panel-header">
                            <h3 class="panel-title">
                                <i class="fas fa-comment-dots"></i>
                                Recent User Feedback
                            </h3>
                            <button class="view-all-btn" id="viewAllUserFeedback">View All</button>
                        </div>
                        <div class="feedback-list" id="analyticsUserFeedbackList">
                            <!-- User feedback will be populated by JavaScript -->
                        </div>
                    </div>

                    <!-- Respondent Experience -->
                    <div class="feedback-panel">
                        <div class="panel-header">
                            <h3 class="panel-title">
                                <i class="fas fa-smile"></i>
                                Respondent Experience
                            </h3>
                            <button class="view-all-btn" id="viewAllExperience">View All</button>
                        </div>
                        <div class="feedback-list" id="analyticsExperienceFeedbackList">
                            <!-- Respondent experience will be populated by JavaScript -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add required styles
        this.addStyles();
    }

    addStyles() {
        if (document.getElementById('analytics-dashboard-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'analytics-dashboard-styles';
        styles.textContent = `
            .analytics-dashboard {
                padding: 20px;
                max-width: 1400px;
                margin: 0 auto;
            }

            .analytics-header {
                background: linear-gradient(135deg, var(--accent-gold) 0%, #E09000 100%);
                color: white;
                padding: 32px;
                border-radius: 16px;
                margin-bottom: 32px;
                box-shadow: 0 10px 30px rgba(26,26,46,0.1);
            }

            .header-content {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 20px;
            }

            .header-title {
                font-family: 'Playfair Display', serif;
                font-size: 2.2rem;
                font-weight: 700;
                margin-bottom: 8px;
            }

            .header-title i {
                margin-right: 12px;
            }

            .header-subtitle {
                font-size: 1rem;
                opacity: 0.9;
            }

            .header-controls {
                display: flex;
                gap: 16px;
                align-items: center;
            }

            .period-selector {
                background: rgba(255,255,255,0.2);
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 8px;
                padding: 8px 16px;
                color: white;
                font-size: 0.9rem;
            }

            .refresh-btn {
                background: rgba(255,255,255,0.2);
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 8px;
                padding: 8px 16px;
                color: white;
                cursor: pointer;
                font-size: 0.9rem;
                transition: background 0.2s ease;
            }

            .refresh-btn:hover {
                background: rgba(255,255,255,0.3);
            }

            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 24px;
                margin-bottom: 32px;
            }

            .metric-card {
                background: var(--bg-elevated);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                border: 1px solid var(--border-default);
            }

            .metric-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
            }

            .metric-title {
                font-size: 0.9rem;
                color: var(--text-secondary);
                font-weight: 500;
            }

            .metric-icon {
                width: 40px;
                height: 40px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.2rem;
            }

            .metric-icon.traffic { 
                background: rgba(245,166,35,0.1); 
                color: var(--accent-gold); 
            }
            
            .metric-icon.users { 
                background: rgba(59,130,246,0.1); 
                color: #3B82F6; 
            }
            
            .metric-icon.surveys { 
                background: rgba(34,197,94,0.1); 
                color: #22C55E; 
            }
            
            .metric-icon.feedback { 
                background: rgba(239,68,68,0.1); 
                color: #EF4444; 
            }

            .metric-value {
                font-size: 2rem;
                font-weight: 700;
                color: var(--text-primary);
                margin-bottom: 8px;
            }

            .metric-change {
                font-size: 0.85rem;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 4px;
            }

            .metric-change.positive { color: #22C55E; }
            .metric-change.negative { color: #EF4444; }
            .metric-change.neutral { color: var(--text-secondary); }

            .charts-section {
                display: grid;
                grid-template-columns: 2fr 1fr;
                gap: 24px;
                margin-bottom: 32px;
            }

            .chart-card {
                background: var(--bg-elevated);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                border: 1px solid var(--border-default);
            }

            .chart-header {
                margin-bottom: 24px;
            }

            .chart-title {
                font-size: 1.2rem;
                font-weight: 600;
                color: var(--text-primary);
            }

            .chart-subtitle {
                font-size: 0.85rem;
                color: var(--text-secondary);
                margin-top: 4px;
            }

            .feedback-panels {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
            }

            .feedback-panel {
                background: var(--bg-elevated);
                border-radius: 16px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                border: 1px solid var(--border-default);
                overflow: hidden;
            }

            .panel-header {
                background: var(--bg-secondary);
                padding: 20px 24px;
                border-bottom: 1px solid var(--border-default);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .panel-title {
                font-size: 1.1rem;
                font-weight: 600;
                color: var(--text-primary);
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .panel-title i {
                color: var(--accent-gold);
            }

            .view-all-btn {
                background: var(--accent-gold);
                color: var(--bg-primary);
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 0.8rem;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.2s ease;
            }

            .view-all-btn:hover {
                background: var(--accent-gold);
                filter: brightness(1.1);
            }

            .feedback-list {
                max-height: 400px;
                overflow-y: auto;
            }

            .feedback-item {
                padding: 16px 24px;
                border-bottom: 1px solid var(--border-default);
                transition: background 0.2s ease;
            }

            .feedback-item:hover {
                background: var(--bg-secondary);
            }

            .feedback-item:last-child {
                border-bottom: none;
            }

            .feedback-meta {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }

            .feedback-type {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 0.7rem;
                font-weight: 500;
            }

            .feedback-type.bug { 
                background: rgba(239,68,68,0.1); 
                color: #EF4444; 
            }
            
            .feedback-type.feature_request { 
                background: rgba(59,130,246,0.1); 
                color: #3B82F6; 
            }
            
            .feedback-type.improvement { 
                background: rgba(245,166,35,0.1); 
                color: var(--accent-gold); 
            }
            
            .feedback-type.general { 
                background: rgba(107,114,128,0.1); 
                color: var(--text-secondary); 
            }

            .feedback-date {
                font-size: 0.75rem;
                color: var(--text-secondary);
            }

            .feedback-content {
                font-size: 0.9rem;
                color: var(--text-primary);
                line-height: 1.5;
            }

            .feedback-title {
                font-weight: 600;
                margin-bottom: 4px;
            }

            .feedback-rating {
                display: flex;
                align-items: center;
                gap: 4px;
                margin-top: 8px;
            }

            .star-rating {
                color: var(--accent-gold);
                font-size: 0.8rem;
            }

            .loading-state {
                text-align: center;
                padding: 40px;
                color: var(--text-secondary);
            }

            .loading-state i {
                font-size: 2rem;
                animation: spin 2s linear infinite;
                margin-bottom: 16px;
            }

            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            .error-state {
                text-align: center;
                padding: 40px;
                color: var(--text-secondary);
            }

            .error-state i {
                font-size: 3rem;
                margin-bottom: 16px;
                color: #EF4444;
            }

            .retry-btn {
                background: var(--accent-gold);
                color: var(--bg-primary);
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                cursor: pointer;
                font-weight: 500;
                margin-top: 16px;
                transition: all 0.2s ease;
            }

            .retry-btn:hover {
                filter: brightness(1.1);
            }

            /* Responsive Design */
            @media (max-width: 1024px) {
                .charts-section {
                    grid-template-columns: 1fr;
                }
                
                .header-content {
                    text-align: center;
                }
                
                .metrics-grid {
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                }

                .feedback-panels {
                    grid-template-columns: 1fr;
                }
            }

            @media (max-width: 768px) {
                .analytics-dashboard {
                    padding: 16px;
                }
                
                .analytics-header {
                    padding: 24px;
                }
                
                .header-title {
                    font-size: 1.8rem;
                }
                
                .metrics-grid {
                    grid-template-columns: 1fr;
                    gap: 16px;
                }
            }
        `;
        
        document.head.appendChild(styles);
    }

    setupEventListeners() {
        const periodSelector = document.getElementById('analyticsperiodSelector');
        const refreshBtn = document.getElementById('analyticsRefreshBtn');
        const viewAllUserFeedback = document.getElementById('viewAllUserFeedback');
        const viewAllExperience = document.getElementById('viewAllExperience');

        if (periodSelector) {
            periodSelector.addEventListener('change', (e) => {
                this.currentPeriod = parseInt(e.target.value);
                this.loadDashboard();
            });
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadDashboard();
            });
        }

        if (viewAllUserFeedback) {
            viewAllUserFeedback.addEventListener('click', () => {
                this.showUserFeedbackModal();
            });
        }

        if (viewAllExperience) {
            viewAllExperience.addEventListener('click', () => {
                this.showExperienceModal();
            });
        }
    }

    async loadDashboard() {
        try {
            this.showLoading();
            
            // Load all data
            const [overview, userFeedback, experienceData] = await Promise.all([
                this.fetchOverview(),
                this.fetchUserFeedback(),
                this.fetchExperienceData()
            ]);

            // Update UI
            this.updateMetrics(overview);
            this.updateCharts(overview);
            this.updateUserFeedback(userFeedback);
            this.updateExperienceData(experienceData);

            this.hideLoading();
        } catch (error) {
            console.error('Dashboard load failed:', error);
            const msg = (error && error.message) ? error.message : '';
            if (msg.includes('403')) {
                this.showError('Access denied: analytics is available for founder/admin accounts only.');
            } else if (msg.includes('401')) {
                this.showError('Session expired. Please sign in again.');
            } else {
                this.showError('Failed to load dashboard data');
            }
        }
    }

    async fetchOverview() {
        const response = await API.get(`/api/dashboard/overview?days=${this.currentPeriod}`);
        return response;
    }

    async fetchUserFeedback() {
        const response = await API.get('/api/dashboard/user-feedback?limit=10');
        return response;
    }

    async fetchExperienceData() {
        const response = await API.get(`/api/dashboard/respondent-experience?days=${this.currentPeriod}`);
        return response;
    }

    updateMetrics(data) {
        const metrics = [
            {
                title: 'Page Views',
                value: this.formatNumber(data.traffic?.page_views || 0),
                icon: 'fas fa-eye',
                iconClass: 'traffic',
                change: this.calculateChange(data.traffic?.page_views, data.traffic?.previous_page_views)
            },
            {
                title: 'Active Users',
                value: this.formatNumber(data.users?.active_users || 0),
                icon: 'fas fa-users',
                iconClass: 'users',
                change: this.calculateChange(data.users?.active_users, data.users?.previous_active_users)
            },
            {
                title: 'Survey Responses',
                value: this.formatNumber(data.surveys?.responses_collected || 0),
                icon: 'fas fa-clipboard-list',
                iconClass: 'surveys',
                change: this.calculateChange(data.surveys?.responses_collected, data.surveys?.previous_responses)
            },
            {
                title: 'User Rating',
                value: (data.feedback?.avg_user_rating || 0).toFixed(1) + '/5',
                icon: 'fas fa-star',
                iconClass: 'feedback',
                change: this.calculateChange(data.feedback?.avg_user_rating, data.feedback?.previous_rating)
            }
        ];

        const grid = document.getElementById('analyticsMetricsGrid');
        if (!grid) return;

        grid.innerHTML = metrics.map(metric => `
            <div class="metric-card">
                <div class="metric-header">
                    <span class="metric-title">${metric.title}</span>
                    <div class="metric-icon ${metric.iconClass}">
                        <i class="${metric.icon}"></i>
                    </div>
                </div>
                <div class="metric-value">${metric.value}</div>
                <div class="metric-change ${metric.change.class}">
                    <i class="fas fa-${metric.change.icon}"></i>
                    ${metric.change.text}
                </div>
            </div>
        `).join('');
    }

    updateCharts(data) {
        // Traffic Trend Chart
        const trafficCtx = document.getElementById('analyticsTrafficChart');
        if (!trafficCtx) return;

        if (this.charts.traffic) {
            this.charts.traffic.destroy();
        }

        this.charts.traffic = new Chart(trafficCtx, {
            type: 'line',
            data: {
                labels: data.daily_trend?.map(d => new Date(d.date).toLocaleDateString()) || [],
                datasets: [
                    {
                        label: 'Page Views',
                        data: data.daily_trend?.map(d => d.page_views) || [],
                        borderColor: '#F5A623',
                        backgroundColor: 'rgba(245,166,35,0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Unique Sessions',
                        data: data.daily_trend?.map(d => d.unique_sessions) || [],
                        borderColor: '#3B82F6',
                        backgroundColor: 'rgba(59,130,246,0.1)',
                        tension: 0.4,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });

        // Channel Performance Chart
        const channelCtx = document.getElementById('analyticsChannelChart');
        if (!channelCtx) return;

        if (this.charts.channel) {
            this.charts.channel.destroy();
        }

        this.charts.channel = new Chart(channelCtx, {
            type: 'doughnut',
            data: {
                labels: ['Web Form', 'Chat', 'Audio'],
                datasets: [{
                    data: [
                        data.surveys?.web_responses || 0,
                        data.surveys?.chat_responses || 0,
                        data.surveys?.audio_responses || 0
                    ],
                    backgroundColor: [
                        '#F5A623',
                        '#3B82F6', 
                        '#22C55E'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    updateUserFeedback(data) {
        const list = document.getElementById('analyticsUserFeedbackList');
        if (!list) return;
        
        if (!data.feedback_items || data.feedback_items.length === 0) {
            list.innerHTML = `
                <div class="loading-state">
                    <i class="fas fa-comment-slash"></i>
                    <p>No user feedback yet</p>
                </div>
            `;
            return;
        }

        list.innerHTML = data.feedback_items.map(item => `
            <div class="feedback-item">
                <div class="feedback-meta">
                    <span class="feedback-type ${item.feedback_type}">
                        ${this.getFeedbackIcon(item.feedback_type)} 
                        ${item.feedback_type.replace('_', ' ')}
                    </span>
                    <span class="feedback-date">${new Date(item.created_at).toLocaleDateString()}</span>
                </div>
                ${item.title ? `<div class="feedback-title">${item.title}</div>` : ''}
                <div class="feedback-content">${item.description}</div>
                ${item.rating ? `
                    <div class="feedback-rating">
                        <span class="star-rating">${'★'.repeat(item.rating)}${'☆'.repeat(5-item.rating)}</span>
                        <span style="font-size: 0.75rem; color: var(--text-secondary);">${item.rating}/5</span>
                    </div>
                ` : ''}
            </div>
        `).join('');
    }

    updateExperienceData(data) {
        const list = document.getElementById('analyticsExperienceFeedbackList');
        if (!list) return;
        
        if (!data.recent_feedback || data.recent_feedback.length === 0) {
            list.innerHTML = `
                <div class="loading-state">
                    <i class="fas fa-smile-wink"></i>
                    <p>No experience feedback yet</p>
                </div>
            `;
            return;
        }

        list.innerHTML = data.recent_feedback.map(item => `
            <div class="feedback-item">
                <div class="feedback-meta">
                    <span class="feedback-type general">
                        <i class="fas fa-microphone"></i> ${item.survey_title}
                    </span>
                    <span class="feedback-date">${new Date(item.created_at).toLocaleDateString()}</span>
                </div>
                ${item.quick_feedback ? `<div class="feedback-content">${item.quick_feedback}</div>` : ''}
                ${item.improvement_suggestion ? `<div class="feedback-content" style="margin-top: 8px; font-style: italic;">Suggestion: ${item.improvement_suggestion}</div>` : ''}
                ${item.overall_rating ? `
                    <div class="feedback-rating">
                        <span class="star-rating">${'★'.repeat(item.overall_rating)}${'☆'.repeat(5-item.overall_rating)}</span>
                        <span style="font-size: 0.75rem; color: var(--text-secondary);">${item.overall_rating}/5</span>
                    </div>
                ` : ''}
            </div>
        `).join('');
    }

    getFeedbackIcon(type) {
        const icons = {
            bug: '<i class="fas fa-bug"></i>',
            feature_request: '<i class="fas fa-lightbulb"></i>',
            improvement: '<i class="fas fa-arrow-up"></i>',
            general: '<i class="fas fa-comment"></i>'
        };
        return icons[type] || icons.general;
    }

    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    calculateChange(current, previous) {
        if (!previous || previous === 0) {
            return { text: 'No previous data', class: 'neutral', icon: 'minus' };
        }

        const change = ((current - previous) / previous * 100);
        
        if (change > 0) {
            return { text: `+${change.toFixed(1)}%`, class: 'positive', icon: 'arrow-up' };
        } else if (change < 0) {
            return { text: `${change.toFixed(1)}%`, class: 'negative', icon: 'arrow-down' };
        } else {
            return { text: '0%', class: 'neutral', icon: 'minus' };
        }
    }

    showLoading() {
        const grid = document.getElementById('analyticsMetricsGrid');
        if (grid) {
            grid.innerHTML = `
                <div class="loading-state" style="grid-column: 1 / -1;">
                    <i class="fas fa-spinner"></i>
                    <p>Loading analytics data...</p>
                </div>
            `;
        }
    }

    hideLoading() {
        // Loading is replaced by actual content
    }

    showError(message) {
        const grid = document.getElementById('analyticsMetricsGrid');
        if (grid) {
            grid.innerHTML = `
                <div class="error-state" style="grid-column: 1 / -1;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>${message}</p>
                    <button class="retry-btn" onclick="App.activeComponent.loadDashboard()">Retry</button>
                </div>
            `;
        }
    }

    showUserFeedbackModal() {
        // Could implement detailed feedback modal
        App.showModal('User Feedback', `
            <p>Detailed user feedback management interface coming soon!</p>
            <p>This will include filtering, status management, and response tracking.</p>
        `, [
            { text: 'Close', action: () => App.hideModal(), primary: false }
        ]);
    }

    showExperienceModal() {
        // Could implement detailed experience modal
        App.showModal('Respondent Experience', `
            <p>Detailed experience analytics interface coming soon!</p>
            <p>This will include experience trends, survey-specific insights, and satisfaction metrics.</p>
        `, [
            { text: 'Close', action: () => App.hideModal(), primary: false }
        ]);
    }

    setupAutoRefresh() {
        // Refresh data every 5 minutes
        this.refreshInterval = setInterval(() => {
            this.loadDashboard();
        }, 5 * 60 * 1000);
    }
}