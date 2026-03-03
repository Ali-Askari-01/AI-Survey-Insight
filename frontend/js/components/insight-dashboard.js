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

    async init() {
        // Load available surveys for the selector
        try { this.surveys = await API.surveys.list(); } catch { this.surveys = []; }
        this.surveyId = App.activeSurveyId || (this.surveys[0]?.id) || 1;
        this.render();
        this.bindEvents();
        await this.loadData();
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
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
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
    }
};
