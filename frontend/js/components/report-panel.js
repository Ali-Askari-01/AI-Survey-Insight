/**
 * Report Panel Component — Executive summaries, recommendations, roadmap
 * Feature 4: Reports & Recommendations
 * Feature 5: Continuous Improvement & Adaptive Feedback
 */
const ReportPanel = {
    currentRole: 'pm',
    currentTab: 'summary',
    surveyId: null,
    surveys: [],

    async init() {
        try { this.surveys = await API.surveys.list(); } catch { this.surveys = []; }
        this.surveyId = App.activeSurveyId || (this.surveys[0]?.id) || 1;
        this.render();
        this.bindEvents();
        await this.loadSummary();
    },

    render() {
        const page = document.getElementById('page-reports');
        if (!page) return;

        const surveyOptions = this.surveys.map(s =>
            `<option value="${s.id}" ${s.id === this.surveyId ? 'selected' : ''}>${Helpers.escapeHtml(s.title || 'Survey #' + s.id)}</option>`
        ).join('');

        page.innerHTML = `
            <div class="report-panel">
                <!-- Survey Selector + Tabs -->
                <div class="flex justify-between align-center mb-3" style="flex-wrap:wrap;gap:var(--space-2)">
                    <select class="filter-select" id="report-survey-select" style="min-width:180px;font-weight:600">
                        ${surveyOptions || '<option value="1">Survey #1</option>'}
                    </select>
                    <div class="tabs">
                        <button class="tab active" data-tab="summary"><i class="fas fa-file-alt"></i> Executive Summary</button>
                        <button class="tab" data-tab="recommendations"><i class="fas fa-clipboard-check"></i> Recommendations</button>
                        <button class="tab" data-tab="matrix"><i class="fas fa-th-large"></i> Impact Matrix</button>
                        <button class="tab" data-tab="roadmap"><i class="fas fa-road"></i> Roadmap</button>
                        <button class="tab" data-tab="export"><i class="fas fa-download"></i> Export</button>
                    </div>
                </div>

                <!-- Tab Panels -->
                <div id="report-tab-content">
                    <div class="spinner"></div>
                </div>
            </div>
        `;
    },

    bindEvents() {
        // Survey selector
        document.getElementById('report-survey-select')?.addEventListener('change', (e) => {
            this.surveyId = parseInt(e.target.value);
            App.activeSurveyId = this.surveyId;
            this.switchTab(this.currentTab);
        });

        document.querySelectorAll('.report-panel .tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.report-panel .tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.currentTab = tab.dataset.tab;
                this.switchTab(this.currentTab);
            });
        });
    },

    async switchTab(tab) {
        switch (tab) {
            case 'summary': await this.loadSummary(); break;
            case 'recommendations': await this.loadRecommendations(); break;
            case 'matrix': await this.loadMatrix(); break;
            case 'roadmap': await this.loadRoadmap(); break;
            case 'export': this.renderExport(); break;
        }
    },

    /* ── Executive Summary ─────────────────────────────── */
    async loadSummary() {
        const container = document.getElementById('report-tab-content');
        if (!container) return;
        container.innerHTML = `
            <div class="card" style="padding:var(--space-4);text-align:center">
                <div class="spinner"></div>
                <p class="text-muted mt-2">Generating executive summary with AI... This may take a moment.</p>
            </div>
        `;

        try {
            const summary = await API.reports.getSummary(this.surveyId, 'professional', 'detailed');
            this.renderSummary(container, summary);
        } catch (e) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-triangle" style="font-size:2rem;color:var(--warning);margin-bottom:var(--space-2)"></i>
                    <p>Failed to load executive summary.</p>
                    <button class="btn btn-primary mt-2" onclick="ReportPanel.loadSummary()"><i class="fas fa-redo"></i> Retry</button>
                </div>
            `;
        }
    },

    renderSummary(container, summary) {
        const s = summary;
        const positivePct = s.positive_pct || 0;
        const neutralPct = s.neutral_pct || 0;
        const negativePct = s.negative_pct || 0;
        const overallSentiment = s.overall_sentiment || 0;

        container.innerHTML = `
            <div class="executive-summary stagger-children">
                <!-- Tone / Length Controls -->
                <div class="summary-controls flex gap-1 mb-3">
                    <div>
                        <label class="text-muted">Tone:</label>
                        <select id="summary-tone" class="filter-select">
                            <option value="professional" selected>Professional</option>
                            <option value="casual">Casual</option>
                            <option value="technical">Technical</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-muted">Length:</label>
                        <select id="summary-length" class="filter-select">
                            <option value="brief">Brief</option>
                            <option value="detailed" selected>Detailed</option>
                            <option value="comprehensive">Comprehensive</option>
                        </select>
                    </div>
                    <button class="btn btn-secondary" id="btn-refresh-summary">
                        <i class="fas fa-sync-alt"></i> Refresh
                    </button>
                </div>

                <!-- Key Metrics -->
                <div class="grid grid-4 gap-2 mb-3">
                    <div class="card stat-card">
                        <div class="stat-icon" style="background:#dbeafe;color:#2563eb"><i class="fas fa-users"></i></div>
                        <div class="stat-content">
                            <div class="stat-value">${Helpers.formatNumber(s.total_responses || 0)}</div>
                            <div class="stat-label">Responses</div>
                        </div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-icon" style="background:#dcfce7;color:var(--success)"><i class="fas fa-smile"></i></div>
                        <div class="stat-content">
                            <div class="stat-value">${positivePct}%</div>
                            <div class="stat-label">Positive Sentiment</div>
                        </div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-icon" style="background:#fef3c7;color:var(--warning)"><i class="fas fa-chart-line"></i></div>
                        <div class="stat-content">
                            <div class="stat-value">${s.response_rate || '—'}%</div>
                            <div class="stat-label">Response Rate</div>
                        </div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-icon" style="background:#ede9fe;color:#7c3aed"><i class="fas fa-lightbulb"></i></div>
                        <div class="stat-content">
                            <div class="stat-value">${s.insight_count || 0}</div>
                            <div class="stat-label">Insights Found</div>
                        </div>
                    </div>
                </div>

                <!-- Narrative Summary -->
                <div class="card mb-3">
                    <div class="card-header"><h3><i class="fas fa-book-reader"></i> Summary Narrative</h3></div>
                    <div class="card-body">
                        <div class="summary-narrative">${this.formatNarrative(s.narrative || s.executive_summary || s.summary || 'No summary available.')}</div>
                    </div>
                </div>

                <!-- Key Findings -->
                <div class="card mb-3">
                    <div class="card-header"><h3><i class="fas fa-search"></i> Key Findings</h3></div>
                    <div class="card-body">
                        <div class="key-findings">
                            ${(s.key_findings || []).length > 0 ? s.key_findings.map(f => `
                                <div class="finding-item">
                                    <i class="fas fa-check-circle" style="color:var(--primary-500)"></i>
                                    <span>${Helpers.escapeHtml(typeof f === 'string' ? f : f.text || JSON.stringify(f))}</span>
                                </div>
                            `).join('') : '<div class="text-muted">No key findings available.</div>'}
                        </div>
                    </div>
                </div>

                <!-- Sentiment Breakdown -->
                <div class="card">
                    <div class="card-header"><h3><i class="fas fa-chart-pie"></i> Sentiment Breakdown</h3></div>
                    <div class="card-body">
                        <div class="sentiment-breakdown flex gap-2">
                            <div class="sentiment-bar-group">
                                <div class="sentiment-bar-label">Positive</div>
                                <div class="progress-bar-container"><div class="progress-bar" style="width:${positivePct}%;background:var(--sentiment-positive)"></div></div>
                                <span>${positivePct}%</span>
                            </div>
                            <div class="sentiment-bar-group">
                                <div class="sentiment-bar-label">Neutral</div>
                                <div class="progress-bar-container"><div class="progress-bar" style="width:${neutralPct}%;background:var(--sentiment-neutral)"></div></div>
                                <span>${neutralPct}%</span>
                            </div>
                            <div class="sentiment-bar-group">
                                <div class="sentiment-bar-label">Negative</div>
                                <div class="progress-bar-container"><div class="progress-bar" style="width:${negativePct}%;background:var(--sentiment-negative)"></div></div>
                                <span>${negativePct}%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Rebind tone/length controls
        document.getElementById('btn-refresh-summary')?.addEventListener('click', async () => {
            const tone = document.getElementById('summary-tone')?.value || 'professional';
            const length = document.getElementById('summary-length')?.value || 'detailed';
            container.innerHTML = `
                <div class="card" style="padding:var(--space-4);text-align:center">
                    <div class="spinner"></div>
                    <p class="text-muted mt-2">Regenerating summary with tone: ${tone}...</p>
                </div>
            `;
            try {
                const newSummary = await API.reports.getSummary(this.surveyId, tone, length);
                this.renderSummary(container, newSummary);
            } catch (e) { Helpers.toast('Error', 'Failed to refresh summary', 'danger'); }
        });
    },

    /* ── Recommendations ───────────────────────────────── */
    async loadRecommendations() {
        const container = document.getElementById('report-tab-content');
        if (!container) return;
        container.innerHTML = '<div class="spinner"></div>';

        try {
            const recs = await API.reports.getRecommendations(this.surveyId);
            this.renderRecommendations(container, recs);
        } catch (e) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle" style="font-size:2rem;color:var(--warning);margin-bottom:var(--space-2)"></i><p>Failed to load recommendations.</p><button class="btn btn-primary mt-2" onclick="ReportPanel.loadRecommendations()"><i class="fas fa-redo"></i> Retry</button></div>';
        }
    },

    renderRecommendations(container, recs) {
        if (!recs || recs.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No recommendations available.</p></div>';
            return;
        }

        const priorityColors = { high: 'var(--danger)', medium: 'var(--warning)', low: 'var(--success)' };
        const statusIcons = { pending: 'fa-clock', in_progress: 'fa-spinner', completed: 'fa-check-circle', dismissed: 'fa-times-circle' };

        container.innerHTML = `
            <div class="recommendations stagger-children">
                <div class="flex justify-between mb-2">
                    <h3>Actionable Recommendations</h3>
                    <div class="flex gap-1">
                        <select id="rec-priority-filter" class="filter-select">
                            <option value="all">All Priorities</option>
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                        </select>
                    </div>
                </div>
                <div class="rec-list">
                    ${recs.map(r => {
                        const priority = r.priority_score >= 0.7 ? 'high' : r.priority_score >= 0.4 ? 'medium' : 'low';
                        return `
                        <div class="card mb-2 rec-card" data-priority="${priority}">
                            <div class="card-body flex gap-2">
                                <div class="rec-priority" style="background:${priorityColors[priority] || 'var(--neutral-400)'}">
                                    ${priority.toUpperCase()}
                                </div>
                                <div class="rec-content" style="flex:1">
                                    <div class="rec-title"><strong>${Helpers.escapeHtml(r.title || 'Recommendation')}</strong></div>
                                    <div class="rec-text text-muted mt-half">${Helpers.escapeHtml(r.description || '')}</div>
                                    <div class="rec-meta flex gap-1 mt-1">
                                        <span class="badge"><i class="fas ${statusIcons[r.status] || 'fa-clock'}"></i> ${(r.status || 'pending').replace('_', ' ')}</span>
                                        <span class="badge">Impact: ${r.impact_score ? (r.impact_score * 10).toFixed(1) : '—'}/10</span>
                                        <span class="badge">Effort: ${r.effort_score ? (r.effort_score * 10).toFixed(1) : '—'}/10</span>
                                        <span class="badge">Timeframe: ${r.timeframe || '—'}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                    }).join('')}
                </div>
            </div>
        `;

        document.getElementById('rec-priority-filter')?.addEventListener('change', (e) => {
            const val = e.target.value;
            document.querySelectorAll('.rec-card').forEach(card => {
                card.style.display = (val === 'all' || card.dataset.priority === val) ? '' : 'none';
            });
        });
    },

    /* ── Impact-Effort Matrix ──────────────────────────── */
    async loadMatrix() {
        const container = document.getElementById('report-tab-content');
        if (!container) return;
        container.innerHTML = '<div class="spinner"></div>';

        try {
            const matrix = await API.reports.getMatrix(this.surveyId);
            this.renderMatrix(container, matrix);
        } catch (e) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle" style="font-size:2rem;color:var(--warning);margin-bottom:var(--space-2)"></i><p>Failed to load impact matrix.</p><button class="btn btn-primary mt-2" onclick="ReportPanel.loadMatrix()"><i class="fas fa-redo"></i> Retry</button></div>';
        }
    },

    renderMatrix(container, matrix) {
        const quadrants = {
            quick_wins: { label: 'Quick Wins', icon: 'fa-bolt', desc: 'High Impact, Low Effort', color: 'var(--success)' },
            major_projects: { label: 'Major Projects', icon: 'fa-project-diagram', desc: 'High Impact, High Effort', color: 'var(--primary-500)' },
            fill_ins: { label: 'Fill-Ins', icon: 'fa-puzzle-piece', desc: 'Low Impact, Low Effort', color: 'var(--warning)' },
            low_priority: { label: 'Low Priority', icon: 'fa-arrow-down', desc: 'Low Impact, High Effort', color: 'var(--neutral-400)' }
        };

        container.innerHTML = `
            <div class="impact-matrix stagger-children">
                <h3 class="mb-2">Impact-Effort Prioritization Matrix</h3>
                <div class="matrix-grid">
                    ${Object.entries(quadrants).map(([key, q]) => `
                        <div class="matrix-quadrant ${key}">
                            <div class="quadrant-header">
                                <i class="fas ${q.icon}" style="color:${q.color}"></i>
                                <span>${q.label}</span>
                                <small class="text-muted">${q.desc}</small>
                            </div>
                            <div class="quadrant-items">
                                ${(matrix[key] || []).map(item => `
                                    <div class="matrix-item">
                                        <span class="matrix-item-title">${Helpers.escapeHtml(item.title || 'Item')}</span>
                                        <div class="flex gap-half">
                                            <span class="badge" style="font-size:0.7rem">I:${((item.impact || item.impact_score || 0) * 10).toFixed(1)}</span>
                                            <span class="badge" style="font-size:0.7rem">E:${((item.effort || item.effort_score || 0) * 10).toFixed(1)}</span>
                                        </div>
                                    </div>
                                `).join('') || '<div class="text-muted">No items</div>'}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    },

    /* ── Roadmap ───────────────────────────────────────── */
    async loadRoadmap() {
        const container = document.getElementById('report-tab-content');
        if (!container) return;
        container.innerHTML = '<div class="spinner"></div>';

        try {
            const roadmap = await API.reports.getRoadmap(this.surveyId);
            this.renderRoadmap(container, roadmap);
        } catch (e) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle" style="font-size:2rem;color:var(--warning);margin-bottom:var(--space-2)"></i><p>Failed to load roadmap.</p><button class="btn btn-primary mt-2" onclick="ReportPanel.loadRoadmap()"><i class="fas fa-redo"></i> Retry</button></div>';
        }
    },

    renderRoadmap(container, roadmap) {
        const phases = [
            { key: 'short', label: 'Short Term (< 1 week)', icon: 'fa-bolt', color: 'var(--success)' },
            { key: 'medium', label: 'Medium Term (2-4 weeks)', icon: 'fa-calendar', color: 'var(--primary-500)' },
            { key: 'long', label: 'Long Term (> 1 month)', icon: 'fa-compass', color: 'var(--warning)' }
        ];

        container.innerHTML = `
            <div class="roadmap-timeline stagger-children">
                <h3 class="mb-2">Implementation Roadmap</h3>
                ${phases.map(phase => {
                    const phaseData = roadmap[phase.key] || {};
                    const items = phaseData.items || [];
                    return `
                    <div class="roadmap-phase">
                        <div class="roadmap-phase-header">
                            <div class="roadmap-dot" style="background:${phase.color}"></div>
                            <h4><i class="fas ${phase.icon}" style="color:${phase.color}"></i> ${phaseData.label || phase.label}</h4>
                        </div>
                        <div class="roadmap-items">
                            ${items.map(item => `
                                <div class="roadmap-item card">
                                    <div class="card-body">
                                        <div class="roadmap-item-title">${Helpers.escapeHtml(item.title || 'Action item')}</div>
                                        <div class="text-muted mt-half">${Helpers.escapeHtml(item.description || '')}</div>
                                        <div class="flex gap-1 mt-1">
                                            <span class="badge">Priority: ${item.priority_score ? (item.priority_score * 10).toFixed(1) : '—'}/10</span>
                                            <span class="badge">Confidence: ${item.confidence ? (item.confidence * 100).toFixed(0) + '%' : '—'}</span>
                                        </div>
                                    </div>
                                </div>
                            `).join('') || '<div class="text-muted" style="padding:var(--space-2)">No items in this phase.</div>'}
                        </div>
                    </div>
                `;
                }).join('')}
            </div>
        `;
    },

    /* ── Export Panel ───────────────────────────────────── */
    renderExport() {
        const container = document.getElementById('report-tab-content');
        if (!container) return;

        container.innerHTML = `
            <div class="export-panel stagger-children">
                <h3 class="mb-2">Export & Integrations</h3>
                <div class="grid grid-2 gap-2">
                    <div class="card export-card" id="export-csv">
                        <div class="card-body" style="text-align:center;padding:var(--space-4)">
                            <i class="fas fa-file-csv" style="font-size:2.5rem;color:var(--success);margin-bottom:var(--space-2)"></i>
                            <h4>CSV Export</h4>
                            <p class="text-muted mt-1">Download all insights and recommendations as a CSV file.</p>
                            <button class="btn btn-success mt-2" id="btn-export-csv">
                                <i class="fas fa-download"></i> Download CSV
                            </button>
                        </div>
                    </div>
                    <div class="card export-card" id="export-jira">
                        <div class="card-body" style="text-align:center;padding:var(--space-4)">
                            <i class="fab fa-jira" style="font-size:2.5rem;color:#0052CC;margin-bottom:var(--space-2)"></i>
                            <h4>Jira Integration</h4>
                            <p class="text-muted mt-1">Push recommendations as Jira tickets to your backlog.</p>
                            <button class="btn btn-primary mt-2" id="btn-export-jira">
                                <i class="fas fa-external-link-alt"></i> Export to Jira
                            </button>
                        </div>
                    </div>
                    <div class="card export-card">
                        <div class="card-body" style="text-align:center;padding:var(--space-4)">
                            <i class="fas fa-sticky-note" style="font-size:2.5rem;color:#000;margin-bottom:var(--space-2)"></i>
                            <h4>Notion Export</h4>
                            <p class="text-muted mt-1">Create a Notion page with the full report and findings.</p>
                            <button class="btn btn-secondary mt-2" id="btn-export-notion">
                                <i class="fas fa-external-link-alt"></i> Export to Notion
                            </button>
                        </div>
                    </div>
                    <div class="card export-card">
                        <div class="card-body" style="text-align:center;padding:var(--space-4)">
                            <i class="fab fa-trello" style="font-size:2.5rem;color:#0079BF;margin-bottom:var(--space-2)"></i>
                            <h4>Trello Export</h4>
                            <p class="text-muted mt-1">Create Trello cards from recommendations.</p>
                            <button class="btn btn-secondary mt-2" id="btn-export-trello">
                                <i class="fas fa-external-link-alt"></i> Export to Trello
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('btn-export-csv')?.addEventListener('click', async () => {
            const sid = ReportPanel.surveyId;
            if (!sid) { Helpers.toast('Warning', 'No survey selected', 'warning'); return; }
            try {
                const csvData = await API.reports.exportCSV(sid);
                if (csvData.rows && csvData.rows.length > 0) {
                    Helpers.downloadCSV(csvData.rows, csvData.filename || 'survey-insights-report.csv');
                    Helpers.toast('Success', 'CSV downloaded!', 'success');
                } else {
                    Helpers.toast('Info', 'No data to export for this survey.', 'info');
                }
            } catch (e) { Helpers.toast('Error', 'Failed to export CSV', 'danger'); }
        });

        document.getElementById('btn-export-jira')?.addEventListener('click', async () => {
            const sid = ReportPanel.surveyId;
            if (!sid) { Helpers.toast('Warning', 'No survey selected', 'warning'); return; }
            try {
                await API.reports.exportJira(sid);
                Helpers.toast('Success', 'Exported to Jira successfully!', 'success');
            } catch (e) {
                Helpers.toast('Info', 'Jira integration demo — connect your Jira instance in settings.', 'info');
            }
        });

        document.getElementById('btn-export-notion')?.addEventListener('click', () => {
            Helpers.toast('Info', 'Notion integration demo — connect your Notion workspace in settings.', 'info');
        });

        document.getElementById('btn-export-trello')?.addEventListener('click', () => {
            Helpers.toast('Info', 'Trello integration demo — connect your Trello board in settings.', 'info');
        });
    },

    formatNarrative(text) {
        let html = Helpers.escapeHtml(text);
        html = html.replace(/\n/g, '<br>');
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        return html;
    },

    destroy() {}
};
