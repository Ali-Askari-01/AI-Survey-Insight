/**
 * Insight Dashboard Component — AI-powered analytics & visualization
 * Feature 3: AI Insight Engine
 */
const InsightDashboard = {
    currentRole: 'pm',
    viewMode: 'explore',
    filters: { sentiment: 'all', theme: 'all', dateRange: '30d', channel: 'all' },
    surveyId: null,
    surveys: [],
    _cachedData: null,
    _storyCache: null,
    _wsListener: null,
    _refreshDebounce: null,

    async init() {
        this.viewMode = App.viewMode || 'explore';
        // Load available surveys for the selector
        try { this.surveys = await API.surveys.list(); } catch { this.surveys = []; }
        this.surveyId = App.activeSurveyId || (this.surveys[0]?.id) || 1;
        this.render();
        this.bindEvents();
        await this.loadData();
        // Initialize Survey Analysis Chatbot
        if (typeof SurveyChatbot !== 'undefined') SurveyChatbot.init(this.surveyId);
        // Subscribe to real-time dashboard updates via WebSocket
        this._setupWebSocket();
    },

    _setupWebSocket() {
        // Connect if not already connected
        API.ws.connect();
        // Remove old listener if any
        if (this._wsListener) API.ws.removeListener(this._wsListener);
        // Create listener for dashboard refresh events
        this._wsListener = (data) => {
            if (data.type === 'dashboard_refresh' && data.survey_id === this.surveyId) {
                // Debounce to avoid rapid refreshes
                clearTimeout(this._refreshDebounce);
                this._refreshDebounce = setTimeout(() => {
                    this.loadData();
                    if (typeof Helpers !== 'undefined' && Helpers.toast) {
                        Helpers.toast('Updated', 'Dashboard refreshed with new data.', 'info', 3000);
                    }
                }, 2000);
            }
        };
        API.ws.onMessage(this._wsListener);
    },

    onViewModeChange(mode) {
        this.viewMode = mode;
        if (mode === 'story') {
            this.renderStoryView();
        } else {
            this.render();
            this.bindEvents();
            this.loadData();
        }
    },

    render() {
        const page = document.getElementById('page-insights');
        if (!page) return;

        const surveyOptions = this.surveys.map(s =>
            `<option value="${s.id}" ${s.id === this.surveyId ? 'selected' : ''}>${Helpers.escapeHtml(s.title || 'Survey #' + s.id)}</option>`
        ).join('');

        page.innerHTML = `
            <!-- Survey Selector + Filter Bar -->
            <div class="filter-bar">
                <div class="filter-chips">
                    <select class="filter-select" id="insight-survey-select" style="min-width:180px;font-weight:600">
                        ${surveyOptions || '<option value="1">Survey #1</option>'}
                    </select>
                    <select class="filter-select" id="filter-sentiment">
                        <option value="all">All Sentiments</option>
                        <option value="positive">Positive</option>
                        <option value="neutral">Neutral</option>
                        <option value="negative">Negative</option>
                    </select>
                    <select class="filter-select" id="filter-theme">
                        <option value="all">All Themes</option>
                    </select>
                    <select class="filter-select" id="filter-channel">
                        <option value="all">All Channels</option>
                        <option value="web_form">Web Form</option>
                        <option value="chat">Chat</option>
                        <option value="voice">Voice</option>
                    </select>
                </div>
            </div>

            <!-- Summary Cards -->
            <div class="grid grid-4 gap-2 mb-3" id="insight-summary-cards">
                <div class="card stat-card"><div class="spinner"></div></div>
                <div class="card stat-card"><div class="spinner"></div></div>
                <div class="card stat-card"><div class="spinner"></div></div>
                <div class="card stat-card"><div class="spinner"></div></div>
            </div>

            <!-- Main Dashboard Grid -->
            <div class="dashboard-grid">
                <!-- Sentiment Trend -->
                <div class="card dashboard-card span-2">
                    <div class="card-header">
                        <h3><i class="fas fa-chart-line"></i> Sentiment Trend</h3>
                    </div>
                    <div class="card-body chart-container">
                        <canvas id="chart-sentiment-trend"></canvas>
                    </div>
                </div>

                <!-- Sentiment Distribution -->
                <div class="card dashboard-card">
                    <div class="card-header">
                        <h3><i class="fas fa-chart-pie"></i> Sentiment Split</h3>
                    </div>
                    <div class="card-body chart-container">
                        <canvas id="chart-sentiment-donut"></canvas>
                    </div>
                </div>

                <!-- Theme Bubbles -->
                <div class="card dashboard-card span-2">
                    <div class="card-header">
                        <h3><i class="fas fa-tags"></i> Theme Landscape</h3>
                    </div>
                    <div class="card-body" id="theme-bubbles-container">
                        <div class="spinner"></div>
                    </div>
                </div>

                <!-- Top Themes Bar Chart -->
                <div class="card dashboard-card">
                    <div class="card-header">
                        <h3><i class="fas fa-chart-bar"></i> Top Themes</h3>
                    </div>
                    <div class="card-body chart-container">
                        <canvas id="chart-themes-bar"></canvas>
                    </div>
                </div>

                <!-- Sentiment Heatmap -->
                <div class="card dashboard-card span-2">
                    <div class="card-header">
                        <h3><i class="fas fa-th"></i> Sentiment Heatmap</h3>
                    </div>
                    <div class="card-body" id="heatmap-container">
                        <div class="spinner"></div>
                    </div>
                </div>

                <!-- Feature Area Impact -->
                <div class="card dashboard-card">
                    <div class="card-header">
                        <h3><i class="fas fa-signal"></i> Feature Area Impact</h3>
                    </div>
                    <div class="card-body chart-container">
                        <canvas id="chart-engagement"></canvas>
                    </div>
                </div>

                <!-- Insight List -->
                <div class="card dashboard-card span-3">
                    <div class="card-header">
                        <h3><i class="fas fa-lightbulb"></i> Key Insights</h3>
                    </div>
                    <div class="card-body" id="insight-list-container">
                        <div class="spinner"></div>
                    </div>
                </div>
            </div>
        `;
    },

    bindEvents() {
        // Survey selector
        document.getElementById('insight-survey-select')?.addEventListener('change', (e) => {
            this.surveyId = parseInt(e.target.value);
            App.activeSurveyId = this.surveyId;
            this.loadData();
            // Update chatbot survey context
            if (typeof SurveyChatbot !== 'undefined') SurveyChatbot.setSurveyId(this.surveyId);
        });

        // Filters
        ['filter-sentiment', 'filter-theme', 'filter-channel'].forEach(id => {
            document.getElementById(id)?.addEventListener('change', () => {
                this.filters.sentiment = document.getElementById('filter-sentiment')?.value || 'all';
                this.filters.theme = document.getElementById('filter-theme')?.value || 'all';
                this.filters.channel = document.getElementById('filter-channel')?.value || 'all';
                this.loadData();
            });
        });
    },

    async loadData() {
        const sid = this.surveyId;
        try {
            const [summary, themes, bubbles, trends, heatmap, insights, patterns] = await Promise.all([
                API.insights.getSummary(sid).catch(() => ({})),
                API.insights.getThemes(sid).catch(() => []),
                API.insights.getBubbles(sid).catch(() => []),
                API.insights.getTrends(sid).catch(() => ({})),
                API.insights.getHeatmap(sid).catch(() => ({})),
                API.insights.get(sid, { sentiment: this.filters.sentiment !== 'all' ? this.filters.sentiment : undefined }).catch(() => []),
                API.insights.getPatterns(sid).catch(() => ({}))
            ]);

            this.renderSummaryCards(summary);
            this.renderSentimentTrend(trends);
            this.renderSentimentDonut(summary);
            this.renderThemeBubbles(bubbles, themes);
            this.renderThemesBar(themes);
            this.renderHeatmap(heatmap);
            this.renderFeatureImpact(summary);
            this.renderInsightList(insights);
            this.populateThemeFilter(themes);

            // Cache data for local story fallback
            this._cachedData = { summary, themes, insights, trends, heatmap, patterns };

        } catch (e) {
            console.error('Failed to load insights:', e);
            Helpers.toast('Error', 'Failed to load insight data', 'danger');
        }
    },

    renderSummaryCards(summary) {
        const container = document.getElementById('insight-summary-cards');
        if (!container) return;

        const totalResponses = summary.total_responses || 0;
        const avgSentiment = summary.avg_sentiment !== undefined ? (summary.avg_sentiment * 100).toFixed(0) : '—';
        const themeCount = summary.total_themes || summary.theme_count || 0;
        const insightCount = summary.total_insights || summary.insight_count || 0;

        container.innerHTML = `
            <div class="card stat-card">
                <div class="stat-icon" style="background: var(--primary-100); color: var(--primary-600)">
                    <i class="fas fa-comments"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${Helpers.formatNumber(totalResponses)}</div>
                    <div class="stat-label">Total Responses</div>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: var(--success-light, #dcfce7); color: var(--success)">
                    <i class="fas fa-heart"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${avgSentiment}%</div>
                    <div class="stat-label">Avg Sentiment</div>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: var(--warning-light, #fef3c7); color: var(--warning)">
                    <i class="fas fa-tags"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${themeCount}</div>
                    <div class="stat-label">Themes Found</div>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: #ede9fe; color: #7c3aed">
                    <i class="fas fa-lightbulb"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${insightCount}</div>
                    <div class="stat-label">Insights</div>
                </div>
            </div>
        `;
    },

    renderSentimentTrend(trendData) {
        const canvas = document.getElementById('chart-sentiment-trend');
        if (!canvas) return;

        // trendData comes from /sentiment/{id}/trends: {feature_area: [{date, sentiment, intensity}]}
        if (trendData && typeof trendData === 'object' && Object.keys(trendData).length > 0) {
            Charts.sentimentTrend('chart-sentiment-trend', trendData);
        } else {
            // Empty state
            canvas.parentElement.innerHTML = '<div class="empty-state"><p>No sentiment trend data available yet.</p></div>';
        }
    },

    renderSentimentDonut(summary) {
        const canvas = document.getElementById('chart-sentiment-donut');
        if (!canvas) return;

        // Use sentiment_distribution from summary: [{sentiment: 'positive', count: N}, ...]
        const dist = summary.sentiment_distribution || [];
        if (dist.length === 0) {
            canvas.parentElement.innerHTML = '<div class="empty-state"><p>No sentiment data yet.</p></div>';
            return;
        }
        const sentMap = {};
        dist.forEach(d => { sentMap[d.sentiment] = d.count; });

        Charts.sentimentDoughnut('chart-sentiment-donut', {
            positive: sentMap.positive || 0,
            neutral: sentMap.neutral || 0,
            negative: sentMap.negative || 0,
            ...(sentMap.mixed ? { mixed: sentMap.mixed } : {})
        });
    },

    renderThemeBubbles(bubbles, themes) {
        const container = document.getElementById('theme-bubbles-container');
        if (!container) return;

        const data = bubbles.length > 0 ? bubbles : themes.map(t => ({
            name: t.name,
            mention_count: t.frequency || t.mention_count || 10,
            avg_sentiment: t.sentiment_avg || t.avg_sentiment || 0.5,
            is_emerging: t.is_emerging || false
        }));

        if (data.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No theme data available yet.</p></div>';
            return;
        }

        const maxCount = Math.max(...data.map(d => d.value || d.mention_count || d.frequency || 1));

        container.innerHTML = `
            <div class="theme-bubble-chart">
                ${data.map(d => {
                    const size = 40 + ((d.value || d.mention_count || d.frequency || 1) / maxCount) * 80;
                    const sentiment = d.sentiment || d.avg_sentiment || 0.5;
                    const color = sentiment > 0.6 ? 'var(--sentiment-positive)' :
                                  sentiment < 0.4 ? 'var(--sentiment-negative)' : 'var(--sentiment-neutral)';
                    return `
                        <div class="theme-bubble ${d.is_emerging ? 'emerging' : ''}"
                             style="width:${size}px;height:${size}px;background:${color}20;border:2px solid ${color};color:${color}"
                             title="${d.name}: ${d.value || d.mention_count || d.frequency || 0} mentions, sentiment ${(sentiment * 100).toFixed(0)}%">
                            <span class="bubble-label">${Helpers.escapeHtml(d.name)}</span>
                            <span class="bubble-count">${d.value || d.mention_count || d.frequency || 0}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    },

    renderThemesBar(themes) {
        const canvas = document.getElementById('chart-themes-bar');
        if (!canvas) return;

        const sorted = [...themes].sort((a, b) => (b.frequency || b.mention_count || 0) - (a.frequency || a.mention_count || 0)).slice(0, 8);
        Charts.themeBar('chart-themes-bar',
            sorted.map(t => t.name),
            sorted.map(t => t.frequency || t.mention_count || 0)
        );
    },

    renderHeatmap(heatmapData) {
        const container = document.getElementById('heatmap-container');
        if (!container) return;

        let themes, periods, matrix;

        if (heatmapData && heatmapData.themes) {
            // Pre-formatted {themes, periods, matrix}
            themes = heatmapData.themes;
            periods = heatmapData.periods;
            matrix = heatmapData.matrix;
        } else if (heatmapData && typeof heatmapData === 'object' && !Array.isArray(heatmapData)) {
            // Backend returns {feature_area: [{date, value}]} 
            themes = Object.keys(heatmapData);
            if (themes.length === 0) {
                container.innerHTML = '<div class="empty-state"><p>No heatmap data available yet.</p></div>';
                return;
            } else {
                const allDates = new Set();
                themes.forEach(t => (heatmapData[t] || []).forEach(p => allDates.add(p.date)));
                const sortedDates = [...allDates].sort();
                // Sample to weekly (every 7th) if more than 10 dates
                if (sortedDates.length > 10) {
                    periods = sortedDates.filter((_, i) => i % 7 === 0 || i === sortedDates.length - 1);
                } else {
                    periods = sortedDates;
                }
                // Format dates for display
                const displayPeriods = periods.map(d => {
                    try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }
                    catch { return d; }
                });
                matrix = themes.map(t => {
                    const dateMap = {};
                    (heatmapData[t] || []).forEach(p => dateMap[p.date] = p.value);
                    return periods.map(d => dateMap[d] !== undefined ? dateMap[d] : 0);
                });
                periods = displayPeriods;
            }
        } else {
            container.innerHTML = '<div class="empty-state"><p>No heatmap data available yet.</p></div>';
            return;
        }

        container.innerHTML = `
            <div class="sentiment-heatmap">
                <div class="heatmap-header">
                    <div class="heatmap-label"></div>
                    ${periods.map(p => `<div class="heatmap-col-label">${p}</div>`).join('')}
                </div>
                ${themes.map((theme, i) => `
                    <div class="heatmap-row">
                        <div class="heatmap-label">${Helpers.escapeHtml(theme)}</div>
                        ${(matrix[i] || []).map(val => {
                            const color = Helpers.sentimentHeatColor(val);
                            return `<div class="heatmap-cell" style="background:${color}" title="${theme}: ${(val * 100).toFixed(0)}%">
                                ${(val * 100).toFixed(0)}
                            </div>`;
                        }).join('')}
                    </div>
                `).join('')}
                <div class="heatmap-legend flex justify-between mt-1">
                    <span class="badge badge-negative">Negative</span>
                    <span class="badge badge-neutral">Neutral</span>
                    <span class="badge badge-positive">Positive</span>
                </div>
            </div>
        `;
    },

    renderFeatureImpact(summary) {
        const canvas = document.getElementById('chart-engagement');
        if (!canvas) return;

        // Use feature_areas from summary: [{feature_area, count, avg_impact}]
        const areas = summary.feature_areas || [];
        if (areas.length === 0) {
            canvas.parentElement.innerHTML = '<div class="empty-state"><p>No feature area data yet.</p></div>';
            return;
        }

        const sorted = [...areas].sort((a, b) => (b.avg_impact || 0) - (a.avg_impact || 0));
        const labels = sorted.map(a => a.feature_area || 'Unknown');
        const impactData = sorted.map(a => Math.round((a.avg_impact || 0) * 100));
        const countData = sorted.map(a => a.count || 0);

        Charts.engagementBar('chart-engagement', labels, countData, impactData);
    },

    renderInsightList(insights) {
        const container = document.getElementById('insight-list-container');
        if (!container) return;

        if (!insights || insights.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-lightbulb" style="font-size:2rem;color:var(--neutral-300);margin-bottom:var(--space-2)"></i><p>No insights found. Run AI analysis on your survey responses to generate insights.</p></div>';
            return;
        }

        container.innerHTML = `
            <div class="insight-list">
                ${insights.map((ins, i) => `
                    <div class="insight-item" data-id="${ins.id}">
                        <div class="insight-rank">#${i + 1}</div>
                        <div class="insight-body">
                            <div class="insight-title">${Helpers.escapeHtml(ins.title || ins.description?.substring(0, 60) || 'Insight')}</div>
                            <div class="insight-text text-muted">${Helpers.escapeHtml(ins.description || '')}</div>
                            <div class="insight-meta flex gap-1 mt-1">
                                ${Helpers.sentimentBadge(ins.sentiment || 'neutral')}
                                ${Helpers.confidenceBar(ins.confidence || 0)}
                                <span class="badge">${Helpers.escapeHtml(ins.feature_area || ins.insight_type || 'General')}</span>
                                ${ins.frequency ? `<span class="badge"><i class="fas fa-users"></i> ${ins.frequency}</span>` : ''}
                                ${ins.impact_score ? `<span class="badge">Impact: ${(ins.impact_score * 10).toFixed(1)}/10</span>` : ''}
                                <button class="badge annotation-btn" data-insight-id="${ins.id}" title="Add annotation"><i class="fas fa-comment-dots"></i> Annotate</button>
                            </div>
                            <div class="insight-annotations" id="annotations-insight-${ins.id}"></div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        // Bind annotation buttons
        container.querySelectorAll('.annotation-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const insightId = e.currentTarget.dataset.insightId;
                this._showAnnotationDialog(insightId, 'insight');
            });
        });

        // Load annotation counts
        this._loadInsightAnnotations(insights);
    },

    async _loadInsightAnnotations(insights) {
        try {
            const annotations = await API.insights.getAnnotations(this.surveyId, 'insight');
            const byTarget = {};
            annotations.forEach(a => {
                if (!byTarget[a.target_id]) byTarget[a.target_id] = [];
                byTarget[a.target_id].push(a);
            });

            Object.entries(byTarget).forEach(([targetId, anns]) => {
                const container = document.getElementById(`annotations-insight-${targetId}`);
                if (container) {
                    container.innerHTML = anns.slice(0, 3).map(a => `
                        <div class="annotation-note" style="border-left: 3px solid ${Helpers.escapeHtml(a.color || '#fbbf24')}">
                            <span class="annotation-author">${Helpers.escapeHtml(a.user_name || 'Anonymous')}</span>
                            <span class="annotation-text">${Helpers.escapeHtml(a.content)}</span>
                            <button class="annotation-delete" data-ann-id="${a.id}" title="Delete"><i class="fas fa-times"></i></button>
                        </div>
                    `).join('') + (anns.length > 3 ? `<span class="annotation-more">+${anns.length - 3} more</span>` : '');

                    // Bind delete buttons
                    container.querySelectorAll('.annotation-delete').forEach(btn => {
                        btn.addEventListener('click', async (e) => {
                            const annId = parseInt(e.currentTarget.dataset.annId);
                            await API.insights.deleteAnnotation(this.surveyId, annId);
                            this.loadData();
                        });
                    });
                }
            });
        } catch (e) {
            console.warn('Failed to load annotations:', e);
        }
    },

    _showAnnotationDialog(targetId, targetType) {
        // Remove existing dialog
        document.getElementById('annotation-dialog')?.remove();

        const dialog = document.createElement('div');
        dialog.id = 'annotation-dialog';
        dialog.className = 'annotation-dialog-overlay';
        dialog.innerHTML = `
            <div class="annotation-dialog">
                <div class="annotation-dialog-header">
                    <h4><i class="fas fa-comment-dots"></i> Add Annotation</h4>
                    <button class="annotation-dialog-close" id="ann-dialog-close"><i class="fas fa-times"></i></button>
                </div>
                <div class="annotation-dialog-body">
                    <input type="text" id="ann-author" class="annotation-input" placeholder="Your name" maxlength="50" value="${localStorage.getItem('annotation_author') || ''}">
                    <textarea id="ann-content" class="annotation-textarea" placeholder="Write your annotation..." maxlength="1000" rows="3"></textarea>
                    <div class="annotation-colors">
                        ${['#fbbf24', '#34d399', '#60a5fa', '#f87171', '#a78bfa'].map(c =>
                            `<button class="annotation-color-btn" data-color="${c}" style="background:${c}"></button>`
                        ).join('')}
                    </div>
                </div>
                <div class="annotation-dialog-footer">
                    <button class="btn btn-sm" id="ann-dialog-cancel">Cancel</button>
                    <button class="btn btn-primary btn-sm" id="ann-dialog-save">Save</button>
                </div>
            </div>
        `;
        document.body.appendChild(dialog);

        let selectedColor = '#fbbf24';
        dialog.querySelectorAll('.annotation-color-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                dialog.querySelectorAll('.annotation-color-btn').forEach(b => b.classList.remove('selected'));
                e.currentTarget.classList.add('selected');
                selectedColor = e.currentTarget.dataset.color;
            });
        });
        // Select first color by default
        dialog.querySelector('.annotation-color-btn')?.classList.add('selected');

        const close = () => dialog.remove();
        dialog.querySelector('#ann-dialog-close').addEventListener('click', close);
        dialog.querySelector('#ann-dialog-cancel').addEventListener('click', close);
        dialog.addEventListener('click', (e) => { if (e.target === dialog) close(); });

        dialog.querySelector('#ann-dialog-save').addEventListener('click', async () => {
            const content = document.getElementById('ann-content')?.value?.trim();
            const author = document.getElementById('ann-author')?.value?.trim() || 'Anonymous';
            if (!content) return;

            localStorage.setItem('annotation_author', author);
            try {
                await API.insights.createAnnotation(this.surveyId, {
                    target_type: targetType,
                    target_id: String(targetId),
                    content,
                    user_name: author,
                    color: selectedColor,
                });
                close();
                this.loadData();
                if (typeof Helpers !== 'undefined' && Helpers.toast) {
                    Helpers.toast('Saved', 'Annotation added.', 'success', 2000);
                }
            } catch (e) {
                console.error('Failed to save annotation:', e);
            }
        });

        // Focus textarea
        setTimeout(() => document.getElementById('ann-content')?.focus(), 100);
    },

    populateThemeFilter(themes) {
        const select = document.getElementById('filter-theme');
        if (!select || select.options.length > 1) return;
        themes.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.name;
            opt.textContent = t.name;
            select.appendChild(opt);
        });
    },

    destroy() {
        Charts.destroy('chart-sentiment-trend');
        Charts.destroy('chart-sentiment-donut');
        Charts.destroy('chart-themes-bar');
        Charts.destroy('chart-engagement');
        // Cleanup WebSocket listener
        if (this._wsListener) {
            API.ws.removeListener(this._wsListener);
            this._wsListener = null;
        }
        clearTimeout(this._refreshDebounce);
        // Cleanup chatbot when leaving insights page
        if (typeof SurveyChatbot !== 'undefined') SurveyChatbot.destroy();
    },

    /* ── Story Mode ─────────────────────────────────────── */
    async renderStoryView() {
        const page = document.getElementById('page-insights');
        if (!page) return;

        // Show loading state
        page.innerHTML = `
            <div class="story-view">
                <div class="story-loading">
                    <div class="story-loading-icon"><i class="fas fa-book-reader fa-3x fa-pulse"></i></div>
                    <p class="story-loading-text">Crafting your insight narrative...</p>
                    <div class="story-loading-bar"><div class="story-loading-progress"></div></div>
                </div>
            </div>
        `;

        try {
            // Fetch story from backend (uses AI generation)
            const story = await API.insights.getStory(this.surveyId);
            this._storyCache = story;
            this._renderStoryContent(page, story);
        } catch (err) {
            console.error('Story generation failed:', err);
            // Fallback: build a local story from cached data
            if (this._cachedData) {
                this._renderLocalStory(page, this._cachedData);
            } else {
                page.innerHTML = `
                    <div class="story-view">
                        <div class="story-section">
                            <div class="story-empty">
                                <i class="fas fa-book-open" style="font-size:3rem;color:var(--neutral-300);margin-bottom:var(--space-3)"></i>
                                <h3>No Story Available Yet</h3>
                                <p class="text-muted">Create surveys and collect responses to generate an insight narrative.</p>
                                <button class="btn btn-primary mt-3" onclick="App.viewMode='explore'; document.querySelectorAll('.view-toggle .view-btn').forEach(b => {b.classList.toggle('active', b.dataset.view==='explore'); b.setAttribute('aria-pressed', b.dataset.view==='explore'?'true':'false');}); document.body.setAttribute('data-view','explore'); InsightDashboard.onViewModeChange('explore');">
                                    <i class="fas fa-compass"></i> Switch to Explore
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }
        }
    },

    _renderStoryContent(page, story) {
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
                <!-- Header Section -->
                <div class="story-section story-header-section">
                    <div class="story-eyebrow"><i class="fas fa-book-open"></i> Insight Narrative — ${Helpers.escapeHtml(story.survey_title || 'Survey')}</div>
                    <h1 class="story-title">${Helpers.escapeHtml(story.headline || 'Survey Insights')}</h1>
                    <p class="story-text story-lead">${Helpers.escapeHtml(story.executive_summary || '')}</p>
                </div>

                <!-- Key Stats -->
                <div class="story-section">
                    <h2 class="story-subtitle"><i class="fas fa-chart-bar"></i> At a Glance</h2>
                    <div class="story-stat-row">
                        <div class="story-stat">
                            <div class="story-stat-value">${Helpers.formatNumber(stats.total_responses || 0)}</div>
                            <div class="story-stat-label">Responses</div>
                        </div>
                        <div class="story-stat">
                            <div class="story-stat-value">${stats.total_themes || 0}</div>
                            <div class="story-stat-label">Themes</div>
                        </div>
                        <div class="story-stat">
                            <div class="story-stat-value">${stats.total_insights || 0}</div>
                            <div class="story-stat-label">Insights</div>
                        </div>
                        <div class="story-stat">
                            <div class="story-stat-value">${stats.total_recommendations || 0}</div>
                            <div class="story-stat-label">Recommendations</div>
                        </div>
                    </div>
                </div>

                <!-- Sentiment Narrative -->
                <div class="story-section">
                    <h2 class="story-subtitle"><i class="fas fa-heart"></i> Sentiment Landscape</h2>
                    <p class="story-text">${Helpers.escapeHtml(story.sentiment_narrative || 'No sentiment data available.')}</p>
                    <div class="story-sentiment-bar">
                        <div class="story-sent-segment story-sent-positive" style="width:${Math.round(pos/total*100)}%">
                            <span>${Math.round(pos/total*100)}%</span>
                        </div>
                        <div class="story-sent-segment story-sent-neutral" style="width:${Math.round(neu/total*100)}%">
                            <span>${Math.round(neu/total*100)}%</span>
                        </div>
                        <div class="story-sent-segment story-sent-negative" style="width:${Math.round(neg/total*100)}%">
                            <span>${Math.round(neg/total*100)}%</span>
                        </div>
                    </div>
                    <div class="story-sentiment-legend">
                        <span><span class="story-legend-dot" style="background:var(--success)"></span> Positive</span>
                        <span><span class="story-legend-dot" style="background:var(--warning)"></span> Neutral</span>
                        <span><span class="story-legend-dot" style="background:var(--danger)"></span> Negative</span>
                    </div>
                </div>

                <!-- Theme Narrative -->
                <div class="story-section">
                    <h2 class="story-subtitle"><i class="fas fa-tags"></i> Theme Discovery</h2>
                    <p class="story-text">${Helpers.escapeHtml(story.theme_narrative || 'No themes discovered yet.')}</p>
                    ${themes.length > 0 ? `
                        <div class="story-theme-pills">
                            ${themes.map(t => {
                                const sentColor = t.sentiment_avg > 0.6 ? 'var(--success)' : t.sentiment_avg < 0.4 ? 'var(--danger)' : 'var(--warning)';
                                return `<div class="story-theme-pill" style="border-left: 3px solid ${sentColor}">
                                    <span class="story-theme-name">${Helpers.escapeHtml(t.name)}</span>
                                    <span class="story-theme-count">${t.frequency || 0} mentions</span>
                                </div>`;
                            }).join('')}
                        </div>
                    ` : ''}
                </div>

                <!-- Key Highlight -->
                ${story.highlight_quote ? `
                <div class="story-section">
                    <div class="story-highlight">
                        <i class="fas fa-quote-left" style="color:var(--warning);margin-right:var(--space-2)"></i>
                        ${Helpers.escapeHtml(story.highlight_quote)}
                    </div>
                </div>
                ` : ''}

                <!-- Key Findings -->
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

                <!-- Recommendations -->
                ${story.recommendations_narrative ? `
                <div class="story-section">
                    <h2 class="story-subtitle"><i class="fas fa-road"></i> What's Next</h2>
                    <p class="story-text">${Helpers.escapeHtml(story.recommendations_narrative)}</p>
                </div>
                ` : ''}

                <!-- Outlook -->
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
    },

    _renderLocalStory(page, data) {
        const { summary, themes, insights } = data;
        const stats = {
            total_responses: summary?.total_responses || 0,
            total_themes: summary?.total_themes || themes?.length || 0,
            total_insights: summary?.total_insights || insights?.length || 0,
            total_recommendations: summary?.feature_areas?.length || 0,
            sentiment_distribution: {}
        };
        (summary?.sentiment_distribution || []).forEach(s => {
            stats.sentiment_distribution[s.sentiment] = s.count;
        });

        const localStory = {
            headline: `${stats.total_insights} Insights from ${stats.total_responses} Responses`,
            executive_summary: `Analysis across ${stats.total_themes} themes revealed ${stats.total_insights} actionable insights from ${stats.total_responses} total responses.`,
            sentiment_narrative: this._buildSentimentNarrative(stats.sentiment_distribution),
            theme_narrative: this._buildThemeNarrative(themes || []),
            key_findings: (insights || []).slice(0, 4).map(i => ({
                title: i.title || i.description?.substring(0, 60) || 'Insight',
                description: i.description || ''
            })),
            highlight_quote: (insights && insights[0]) ? (insights[0].description || insights[0].title || '') : '',
            recommendations_narrative: 'Review the key findings above and prioritize actions based on impact scores and sentiment trends.',
            outlook: 'Continue collecting responses to strengthen confidence levels and uncover emerging themes.',
            stats,
            themes: (themes || []).slice(0, 8).map(t => ({
                name: t.name,
                frequency: t.frequency || t.mention_count || 0,
                sentiment_avg: t.sentiment_avg || t.avg_sentiment || 0.5
            })),
            survey_title: 'Survey #' + this.surveyId
        };
        this._renderStoryContent(page, localStory);
    },

    _buildSentimentNarrative(dist) {
        const pos = dist.positive || 0;
        const neu = dist.neutral || 0;
        const neg = dist.negative || 0;
        const total = pos + neu + neg || 1;
        const pPct = Math.round(pos / total * 100);
        const nPct = Math.round(neg / total * 100);
        if (total <= 1) return 'Not enough data to determine sentiment patterns.';
        if (pPct > 60) return `Sentiment is strongly positive at ${pPct}%, indicating high user satisfaction across most topics.`;
        if (nPct > 40) return `A notable ${nPct}% of feedback carries negative sentiment, highlighting areas that need attention.`;
        return `Sentiment is mixed: ${pPct}% positive, ${Math.round(neu/total*100)}% neutral, and ${nPct}% negative.`;
    },

    _buildThemeNarrative(themes) {
        if (themes.length === 0) return 'No themes have been identified yet.';
        const top3 = themes.slice(0, 3).map(t => t.name);
        return `${themes.length} themes were discovered. The most prominent are ${top3.join(', ')}. ` +
            `The leading theme "${top3[0]}" appeared ${themes[0]?.frequency || themes[0]?.mention_count || 0} times across responses.`;
    }
};
