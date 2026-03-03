/**
 * My Surveys Component — Survey Management Dashboard
 * Shows all user surveys: drafts, active, completed
 * Displays share links, respondent counts, analytics, and transcripts
 */
const MySurveys = {
    surveys: [],
    selectedSurvey: null,
    view: 'list', // list | detail | analytics | transcripts

    async init() {
        this.view = 'list';
        this.selectedSurvey = null;
        this.render();
        await this.loadSurveys();
    },

    render() {
        const page = document.getElementById('page-my-surveys');
        if (!page) return;
        page.innerHTML = `
            <div class="my-surveys">
                <div id="my-surveys-content">
                    <div style="text-align:center;padding:var(--space-6)"><div class="spinner"></div><p class="text-muted mt-2">Loading surveys...</p></div>
                </div>
            </div>
        `;
    },

    async loadSurveys() {
        try {
            this.surveys = await API.publish.mySurveys();
            this.renderList();
        } catch (e) {
            console.error('Failed to load surveys:', e);
            document.getElementById('my-surveys-content').innerHTML = `
                <div class="card" style="padding:var(--space-4);text-align:center">
                    <i class="fas fa-exclamation-circle" style="font-size:2rem;color:var(--danger)"></i>
                    <p class="mt-2">Failed to load surveys. Please try again.</p>
                    <button class="btn btn-primary mt-2" onclick="MySurveys.loadSurveys()">Retry</button>
                </div>
            `;
        }
    },

    renderList() {
        const container = document.getElementById('my-surveys-content');
        if (!container) return;

        const drafts = this.surveys.filter(s => !s.publication || s.publication.status === 'draft');
        const active = this.surveys.filter(s => s.publication && s.publication.status === 'active');
        const closed = this.surveys.filter(s => s.publication && s.publication.status === 'closed');

        container.innerHTML = `
            <!-- Header -->
            <div class="flex justify-between align-center mb-3">
                <div>
                    <h2 style="margin:0"><i class="fas fa-folder-open" style="color:var(--primary-500)"></i> My Surveys</h2>
                    <p class="text-muted mt-1">Manage your surveys, share links, view respondents and transcripts</p>
                </div>
                <button class="btn btn-primary" onclick="window.location.hash='survey-designer'">
                    <i class="fas fa-plus"></i> New Survey
                </button>
            </div>

            <!-- Stats Row -->
            <div class="grid grid-4 gap-2 mb-3">
                <div class="card stat-card">
                    <div class="stat-icon" style="background:var(--primary-100);color:var(--primary-600)"><i class="fas fa-poll"></i></div>
                    <div class="stat-content"><div class="stat-value">${this.surveys.length}</div><div class="stat-label">Total Surveys</div></div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="background:#dcfce7;color:var(--success)"><i class="fas fa-broadcast-tower"></i></div>
                    <div class="stat-content"><div class="stat-value">${active.length}</div><div class="stat-label">Active</div></div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="background:#fef3c7;color:var(--warning)"><i class="fas fa-pencil-ruler"></i></div>
                    <div class="stat-content"><div class="stat-value">${drafts.length}</div><div class="stat-label">Drafts</div></div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="background:#ede9fe;color:#7c3aed"><i class="fas fa-users"></i></div>
                    <div class="stat-content"><div class="stat-value">${this.surveys.reduce((a, s) => a + (s.respondent_count || 0), 0)}</div><div class="stat-label">Total Respondents</div></div>
                </div>
            </div>

            <!-- Active Surveys -->
            ${active.length > 0 ? `
                <h3 class="mb-2" style="color:var(--success)"><i class="fas fa-broadcast-tower"></i> Active Surveys</h3>
                <div class="grid grid-1 gap-2 mb-3">${active.map(s => this._renderSurveyCard(s, 'active')).join('')}</div>
            ` : ''}

            <!-- Draft Surveys -->
            ${drafts.length > 0 ? `
                <h3 class="mb-2" style="color:var(--warning)"><i class="fas fa-pencil-ruler"></i> Drafts</h3>
                <div class="grid grid-1 gap-2 mb-3">${drafts.map(s => this._renderSurveyCard(s, 'draft')).join('')}</div>
            ` : ''}

            <!-- Closed Surveys -->
            ${closed.length > 0 ? `
                <h3 class="mb-2" style="color:var(--neutral-500)"><i class="fas fa-archive"></i> Closed</h3>
                <div class="grid grid-1 gap-2 mb-3">${closed.map(s => this._renderSurveyCard(s, 'closed')).join('')}</div>
            ` : ''}

            ${this.surveys.length === 0 ? `
                <div class="card" style="text-align:center;padding:var(--space-6)">
                    <i class="fas fa-clipboard-list" style="font-size:3rem;color:var(--neutral-400)"></i>
                    <h3 class="mt-2">No Surveys Yet</h3>
                    <p class="text-muted">Create your first survey using the AI Survey Designer</p>
                    <button class="btn btn-primary mt-2" onclick="window.location.hash='survey-designer'">
                        <i class="fas fa-magic"></i> Create Survey
                    </button>
                </div>
            ` : ''}
        `;
    },

    _renderSurveyCard(survey, statusType) {
        const statusColors = { active: 'var(--success)', draft: 'var(--warning)', closed: 'var(--neutral-500)' };
        const statusIcons = { active: 'fa-broadcast-tower', draft: 'fa-pencil-ruler', closed: 'fa-archive' };
        const statusLabels = { active: 'Active', draft: 'Draft', closed: 'Closed' };
        const borderColor = statusColors[statusType] || 'var(--border)';

        const pub = survey.publication;
        const links = survey.links;
        const baseUrl = window.location.origin;

        return `
            <div class="card" style="border-left:4px solid ${borderColor};overflow:hidden">
                <div style="padding:var(--space-4)">
                    <div class="flex justify-between align-center">
                        <div style="flex:1">
                            <div class="flex align-center gap-2">
                                <h3 style="margin:0">${Helpers.escapeHtml(survey.title || 'Untitled Survey')}</h3>
                                <span class="badge" style="background:${borderColor}20;color:${borderColor};font-size:0.75rem;padding:2px 8px;border-radius:12px">
                                    <i class="fas ${statusIcons[statusType]}"></i> ${statusLabels[statusType]}
                                </span>
                            </div>

                            <div class="flex gap-3 mt-2" style="font-size:0.85rem;color:var(--neutral-500)">
                                <span><i class="fas fa-list"></i> ${survey.question_count || 0} questions</span>
                                <span><i class="fas fa-users"></i> ${survey.respondent_count || 0} respondents</span>
                                <span><i class="fas fa-check-circle"></i> ${survey.completed_count || 0} completed</span>
                                <span><i class="fas fa-clock"></i> ${survey.estimated_duration || 5} min</span>
                            </div>
                        </div>
                        <div class="flex gap-1">
                            ${statusType === 'draft' && (survey.question_count || 0) > 0 ? `
                                <button class="btn btn-primary btn-sm" onclick="MySurveys.publishSurvey(${survey.id})">
                                    <i class="fas fa-rocket"></i> Publish
                                </button>
                            ` : ''}
                            ${statusType === 'active' ? `
                                <button class="btn btn-secondary btn-sm" onclick="MySurveys.showLinks(${survey.id})">
                                    <i class="fas fa-share-alt"></i> Links
                                </button>
                                <button class="btn btn-sm" style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white" onclick="MySurveys.showAnalysis(${survey.id})">
                                    <i class="fas fa-brain"></i> Analysis
                                </button>
                                <button class="btn btn-secondary btn-sm" onclick="MySurveys.showExport(${survey.id})" title="Export Data">
                                    <i class="fas fa-download"></i>
                                </button>
                                <button class="btn btn-sm" style="background:#ec4899;color:white" onclick="MySurveys.showEmailInvite(${survey.id})" title="Email Invitations">
                                    <i class="fas fa-envelope"></i>
                                </button>
                            ` : ''}
                            <button class="btn btn-secondary btn-sm" onclick="MySurveys.showRespondents(${survey.id})">
                                <i class="fas fa-users"></i> Respondents
                            </button>
                        </div>
                    </div>

                    <!-- Share Links (for active surveys) -->
                    ${statusType === 'active' && links ? `
                        <div style="margin-top:var(--space-3);padding:var(--space-3);background:var(--neutral-50);border-radius:var(--radius-md)">
                            <div style="font-size:0.85rem;font-weight:600;margin-bottom:var(--space-2)"><i class="fas fa-link"></i> Share Interview Links</div>
                            <div class="grid grid-3 gap-2">
                                ${pub.web_form_enabled ? `
                                    <div class="flex align-center gap-1" style="font-size:0.8rem">
                                        <i class="fas fa-clipboard-list" style="color:var(--primary-500)"></i>
                                        <input type="text" value="${baseUrl}${links.web_form}" readonly style="flex:1;font-size:0.75rem;padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:white" onclick="this.select()">
                                        <button class="btn btn-sm" style="padding:4px 8px" onclick="MySurveys.copyLink('${baseUrl}${links.web_form}')"><i class="fas fa-copy"></i></button>
                                    </div>
                                ` : ''}
                                ${pub.chat_enabled ? `
                                    <div class="flex align-center gap-1" style="font-size:0.8rem">
                                        <i class="fas fa-comments" style="color:#8b5cf6"></i>
                                        <input type="text" value="${baseUrl}${links.chat}" readonly style="flex:1;font-size:0.75rem;padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:white" onclick="this.select()">
                                        <button class="btn btn-sm" style="padding:4px 8px" onclick="MySurveys.copyLink('${baseUrl}${links.chat}')"><i class="fas fa-copy"></i></button>
                                    </div>
                                ` : ''}
                                ${pub.audio_enabled ? `
                                    <div class="flex align-center gap-1" style="font-size:0.8rem">
                                        <i class="fas fa-microphone" style="color:var(--warning)"></i>
                                        <input type="text" value="${baseUrl}${links.audio}" readonly style="flex:1;font-size:0.75rem;padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:white" onclick="this.select()">
                                        <button class="btn btn-sm" style="padding:4px 8px" onclick="MySurveys.copyLink('${baseUrl}${links.audio}')"><i class="fas fa-copy"></i></button>
                                    </div>
                                ` : ''}
                            </div>
                            <div style="margin-top:var(--space-2)">
                                <a href="${links.landing}" target="_blank" class="btn btn-sm btn-primary" style="font-size:0.8rem">
                                    <i class="fas fa-external-link-alt"></i> Open Landing Page
                                </a>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    },

    copyLink(link) {
        navigator.clipboard.writeText(link).then(() => {
            Helpers.toast('Copied!', 'Interview link copied to clipboard', 'success', 2000);
        }).catch(() => {
            // Fallback
            const t = document.createElement('textarea');
            t.value = link;
            document.body.appendChild(t);
            t.select();
            document.execCommand('copy');
            document.body.removeChild(t);
            Helpers.toast('Copied!', 'Interview link copied to clipboard', 'success', 2000);
        });
    },

    async publishSurvey(surveyId) {
        const btn = event?.target?.closest?.('button');
        const resetBtn = Helpers.btnLoading(btn, 'Publishing...');
        try {
            const result = await API.publish.publish({ survey_id: surveyId });
            Helpers.toast('Published!', 'Survey is now live. Share the links with your respondents.', 'success');
            await this.loadSurveys();
        } catch (e) {
            Helpers.toast('Error', e.message || 'Failed to publish', 'error');
        } finally {
            resetBtn();
        }
    },

    showLinks(surveyId) {
        const survey = this.surveys.find(s => s.id === surveyId);
        if (!survey || !survey.links) return;

        const baseUrl = window.location.origin;
        const links = survey.links;
        const pub = survey.publication;

        Helpers.openModal('Share Interview Links', `
            <div style="padding:var(--space-3)">
                <p class="text-muted mb-3">Share these links with your respondents. Each link opens a different interview experience:</p>

                ${pub.web_form_enabled ? `
                <div class="card mb-2" style="padding:var(--space-3);border-left:4px solid var(--primary-500)">
                    <div class="flex align-center gap-2 mb-1">
                        <i class="fas fa-clipboard-list fa-lg" style="color:var(--primary-500)"></i>
                        <strong>Web Form Interview</strong>
                    </div>
                    <p class="text-muted" style="font-size:0.85rem">Progressive conversational form — clean, focused experience</p>
                    <div class="flex gap-1 mt-2">
                        <input type="text" value="${baseUrl}${links.web_form}" readonly style="flex:1;padding:8px;border:1px solid var(--border);border-radius:var(--radius-md)" onclick="this.select()">
                        <button class="btn btn-primary btn-sm" onclick="MySurveys.copyLink('${baseUrl}${links.web_form}')"><i class="fas fa-copy"></i> Copy</button>
                    </div>
                </div>
                ` : ''}

                ${pub.chat_enabled ? `
                <div class="card mb-2" style="padding:var(--space-3);border-left:4px solid #8b5cf6">
                    <div class="flex align-center gap-2 mb-1">
                        <i class="fas fa-comments fa-lg" style="color:#8b5cf6"></i>
                        <strong>Chat Interview</strong>
                    </div>
                    <p class="text-muted" style="font-size:0.85rem">WhatsApp-style AI chat — natural conversation flow</p>
                    <div class="flex gap-1 mt-2">
                        <input type="text" value="${baseUrl}${links.chat}" readonly style="flex:1;padding:8px;border:1px solid var(--border);border-radius:var(--radius-md)" onclick="this.select()">
                        <button class="btn btn-primary btn-sm" onclick="MySurveys.copyLink('${baseUrl}${links.chat}')"><i class="fas fa-copy"></i> Copy</button>
                    </div>
                </div>
                ` : ''}

                ${pub.audio_enabled ? `
                <div class="card mb-2" style="padding:var(--space-3);border-left:4px solid var(--warning)">
                    <div class="flex align-center gap-2 mb-1">
                        <i class="fas fa-microphone fa-lg" style="color:var(--warning)"></i>
                        <strong>Audio Interview</strong>
                    </div>
                    <p class="text-muted" style="font-size:0.85rem">Voice-based — respondent speaks, AI transcribes everything</p>
                    <div class="flex gap-1 mt-2">
                        <input type="text" value="${baseUrl}${links.audio}" readonly style="flex:1;padding:8px;border:1px solid var(--border);border-radius:var(--radius-md)" onclick="this.select()">
                        <button class="btn btn-primary btn-sm" onclick="MySurveys.copyLink('${baseUrl}${links.audio}')"><i class="fas fa-copy"></i> Copy</button>
                    </div>
                </div>
                ` : ''}

                <div class="card mt-3" style="padding:var(--space-3);background:var(--neutral-50)">
                    <div class="flex align-center gap-2 mb-1">
                        <i class="fas fa-link fa-lg" style="color:var(--primary-500)"></i>
                        <strong>General Landing Page</strong>
                    </div>
                    <p class="text-muted" style="font-size:0.85rem">Respondent chooses their preferred interview method</p>
                    <div class="flex gap-1 mt-2">
                        <input type="text" value="${baseUrl}${links.landing}" readonly style="flex:1;padding:8px;border:1px solid var(--border);border-radius:var(--radius-md)" onclick="this.select()">
                        <button class="btn btn-primary btn-sm" onclick="MySurveys.copyLink('${baseUrl}${links.landing}')"><i class="fas fa-copy"></i> Copy</button>
                    </div>
                </div>
            </div>
        `);
    },

    async showAnalysis(surveyId) {
        const survey = this.surveys.find(s => s.id === surveyId);
        Helpers.openModal(`AI Analysis — ${survey?.title || 'Survey'}`, `
            <div style="padding:var(--space-4);text-align:center">
                <div class="spinner" style="margin:0 auto var(--space-3)"></div>
                <h3 style="color:var(--primary-600)"><i class="fas fa-brain"></i> Generating AI Analysis...</h3>
                <p class="text-muted">Analyzing all interview transcripts. This may take 15-30 seconds.</p>
            </div>
        `);

        try {
            const data = await API.publish.analysis(surveyId);

            if (!data.has_data) {
                document.querySelector('.modal-body').innerHTML = `
                    <div style="padding:var(--space-4);text-align:center">
                        <i class="fas fa-inbox" style="font-size:3rem;color:var(--neutral-400)"></i>
                        <h3 class="mt-2" style="color:var(--neutral-600)">No Interview Data Yet</h3>
                        <p class="text-muted">${data.message || 'Share your survey link and wait for respondents to complete interviews.'}</p>
                        <div class="flex gap-2 justify-center mt-3" style="font-size:0.85rem">
                            <span><i class="fas fa-users"></i> ${data.total_respondents || 0} respondents</span>
                            <span><i class="fas fa-check-circle"></i> ${data.completed || 0} completed</span>
                        </div>
                    </div>`;
                return;
            }

            const a = data.analysis;
            const sentColor = a.sentiment_overview?.overall === 'positive' ? 'var(--success)' : a.sentiment_overview?.overall === 'negative' ? 'var(--danger)' : 'var(--warning)';

            document.querySelector('.modal-body').innerHTML = `
                <div style="padding:var(--space-3);max-height:75vh;overflow-y:auto">
                    <!-- Header Stats -->
                    <div class="grid grid-3 gap-2 mb-3">
                        <div class="card" style="text-align:center;padding:var(--space-3)">
                            <div style="font-size:1.8rem;font-weight:700;color:var(--primary-500)">${data.total_respondents}</div>
                            <div class="text-muted" style="font-size:0.8rem">Respondents</div>
                        </div>
                        <div class="card" style="text-align:center;padding:var(--space-3)">
                            <div style="font-size:1.8rem;font-weight:700;color:var(--success)">${data.completed}</div>
                            <div class="text-muted" style="font-size:0.8rem">Completed</div>
                        </div>
                        <div class="card" style="text-align:center;padding:var(--space-3)">
                            <div style="font-size:1.8rem;font-weight:700;color:${sentColor}">${a.sentiment_overview?.overall || '—'}</div>
                            <div class="text-muted" style="font-size:0.8rem">Overall Sentiment</div>
                        </div>
                    </div>

                    <!-- Executive Summary -->
                    <div class="card mb-3" style="padding:var(--space-3);border-left:4px solid var(--primary-500);background:linear-gradient(135deg,#f0f4ff,#ede9fe)">
                        <h4 style="margin:0 0 var(--space-2) 0;color:var(--primary-700)"><i class="fas fa-file-alt"></i> Executive Summary</h4>
                        <div style="font-size:0.9rem;line-height:1.7;white-space:pre-line">${Helpers.escapeHtml(a.executive_summary || '')}</div>
                    </div>

                    <!-- Key Findings -->
                    ${a.key_findings?.length > 0 ? `
                        <h4 class="mb-2"><i class="fas fa-lightbulb" style="color:var(--warning)"></i> Key Findings</h4>
                        <div class="mb-3">
                            ${a.key_findings.map((f, i) => `
                                <div class="card mb-2" style="padding:var(--space-3);border-left:4px solid ${f.impact === 'high' ? 'var(--danger)' : f.impact === 'medium' ? 'var(--warning)' : 'var(--success)'}">
                                    <div class="flex justify-between align-center mb-1">
                                        <strong style="font-size:0.9rem">${i+1}. ${Helpers.escapeHtml(f.finding)}</strong>
                                        <span class="badge" style="font-size:0.7rem;padding:2px 8px;background:${f.impact === 'high' ? '#fef2f2' : f.impact === 'medium' ? '#fef3c7' : '#dcfce7'};color:${f.impact === 'high' ? 'var(--danger)' : f.impact === 'medium' ? 'var(--warning)' : 'var(--success)'}">${f.impact} impact</span>
                                    </div>
                                    <p style="font-size:0.85rem;color:var(--neutral-600);margin:0">${Helpers.escapeHtml(f.evidence || '')}</p>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    <!-- Pain Points -->
                    ${a.pain_points?.length > 0 ? `
                        <h4 class="mb-2"><i class="fas fa-exclamation-triangle" style="color:var(--danger)"></i> Pain Points</h4>
                        <div class="mb-3">
                            ${a.pain_points.map(p => `
                                <div class="card mb-2" style="padding:var(--space-2) var(--space-3);border-left:3px solid ${p.severity === 'critical' ? 'var(--danger)' : p.severity === 'major' ? 'var(--warning)' : 'var(--neutral-400)'}">
                                    <div class="flex justify-between align-center">
                                        <strong style="font-size:0.85rem">${Helpers.escapeHtml(p.issue)}</strong>
                                        <span style="font-size:0.75rem;color:var(--neutral-500)">${p.severity} · ${p.frequency || ''}</span>
                                    </div>
                                    ${p.example_quotes?.length > 0 ? `<div style="font-size:0.8rem;font-style:italic;color:var(--neutral-500);margin-top:4px">"${Helpers.escapeHtml(p.example_quotes[0])}"</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    <!-- Positive Aspects -->
                    ${a.positive_aspects?.length > 0 ? `
                        <h4 class="mb-2"><i class="fas fa-thumbs-up" style="color:var(--success)"></i> Positive Aspects</h4>
                        <div class="mb-3">
                            ${a.positive_aspects.map(p => `
                                <div class="card mb-2" style="padding:var(--space-2) var(--space-3);border-left:3px solid var(--success)">
                                    <strong style="font-size:0.85rem">${Helpers.escapeHtml(p.aspect)}</strong>
                                    <span style="font-size:0.75rem;color:var(--neutral-500);margin-left:8px">${p.frequency || ''}</span>
                                    ${p.example_quotes?.length > 0 ? `<div style="font-size:0.8rem;font-style:italic;color:var(--neutral-500);margin-top:4px">"${Helpers.escapeHtml(p.example_quotes[0])}"</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    <!-- Per-Question Analysis -->
                    ${a.per_question_analysis?.length > 0 ? `
                        <h4 class="mb-2"><i class="fas fa-list-ol" style="color:var(--primary-500)"></i> Per-Question Analysis</h4>
                        <div class="mb-3" style="max-height:300px;overflow-y:auto">
                            ${a.per_question_analysis.map((q, i) => `
                                <div class="card mb-2" style="padding:var(--space-3)">
                                    <div class="flex justify-between align-center mb-1">
                                        <strong style="font-size:0.85rem">Q${i+1}. ${Helpers.escapeHtml((q.question || '').substring(0, 100))}</strong>
                                        <span class="badge" style="font-size:0.7rem;padding:2px 6px;background:${q.sentiment === 'positive' ? '#dcfce7' : q.sentiment === 'negative' ? '#fef2f2' : '#fef3c7'};color:${q.sentiment === 'positive' ? 'var(--success)' : q.sentiment === 'negative' ? 'var(--danger)' : 'var(--warning)'}">${q.sentiment}</span>
                                    </div>
                                    <p style="font-size:0.85rem;color:var(--neutral-600);margin:0 0 4px 0">${Helpers.escapeHtml(q.response_pattern || '')}</p>
                                    ${q.common_themes?.length > 0 ? `<div class="flex gap-1 flex-wrap">${q.common_themes.map(t => `<span class="badge" style="font-size:0.7rem;padding:2px 6px;background:var(--primary-100);color:var(--primary-600)">${Helpers.escapeHtml(t)}</span>`).join('')}</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    <!-- Themes -->
                    ${a.themes_discovered?.length > 0 ? `
                        <h4 class="mb-2"><i class="fas fa-tags" style="color:#7c3aed"></i> Themes Discovered</h4>
                        <div class="flex gap-1 flex-wrap mb-3">
                            ${a.themes_discovered.map(t => `
                                <span class="badge" style="padding:5px 12px;font-size:0.8rem;background:#ede9fe;color:#7c3aed;border-radius:12px">
                                    ${Helpers.escapeHtml(t.theme)} ${t.frequency ? `(${t.frequency})` : ''}
                                </span>
                            `).join('')}
                        </div>
                    ` : ''}

                    <!-- Recommendations -->
                    ${a.recommendations?.length > 0 ? `
                        <h4 class="mb-2"><i class="fas fa-clipboard-check" style="color:var(--primary-500)"></i> Recommendations</h4>
                        <div class="mb-3">
                            ${a.recommendations.map((r, i) => `
                                <div class="card mb-2" style="padding:var(--space-3);border-left:4px solid ${r.priority === 'high' ? 'var(--danger)' : r.priority === 'medium' ? 'var(--warning)' : 'var(--success)'}">
                                    <div class="flex justify-between align-center mb-1">
                                        <strong style="font-size:0.9rem">${i+1}. ${Helpers.escapeHtml(r.title)}</strong>
                                        <div class="flex gap-1">
                                            <span class="badge" style="font-size:0.7rem;padding:2px 6px;background:${r.priority === 'high' ? '#fef2f2;color:var(--danger)' : r.priority === 'medium' ? '#fef3c7;color:var(--warning)' : '#dcfce7;color:var(--success)'}">${r.priority}</span>
                                            ${r.category ? `<span class="badge" style="font-size:0.7rem;padding:2px 6px;background:var(--neutral-100);color:var(--neutral-600)">${r.category}</span>` : ''}
                                        </div>
                                    </div>
                                    <p style="font-size:0.85rem;color:var(--neutral-600);margin:0">${Helpers.escapeHtml(r.description)}</p>
                                    ${r.expected_impact ? `<p style="font-size:0.8rem;color:var(--primary-500);margin:4px 0 0"><i class="fas fa-chart-line"></i> ${Helpers.escapeHtml(r.expected_impact)}</p>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    <!-- Respondent Segments -->
                    ${a.respondent_segments?.length > 0 ? `
                        <h4 class="mb-2"><i class="fas fa-users" style="color:var(--primary-500)"></i> Respondent Segments</h4>
                        <div class="grid grid-2 gap-2 mb-3">
                            ${a.respondent_segments.map(s => `
                                <div class="card" style="padding:var(--space-3)">
                                    <strong style="font-size:0.9rem">${Helpers.escapeHtml(s.segment)}</strong>
                                    <span style="font-size:0.75rem;color:var(--neutral-500);margin-left:8px">${s.size || ''}</span>
                                    <p style="font-size:0.85rem;color:var(--neutral-600);margin:4px 0">${Helpers.escapeHtml(s.description || '')}</p>
                                    ${s.key_characteristics?.length > 0 ? `<div class="flex gap-1 flex-wrap">${s.key_characteristics.map(c => `<span class="badge" style="font-size:0.7rem;padding:2px 6px">${Helpers.escapeHtml(c)}</span>`).join('')}</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    <div style="text-align:center;padding:var(--space-2);font-size:0.8rem;color:var(--neutral-400)">
                        <i class="fas fa-info-circle"></i> Based on ${data.transcripts_analyzed} interview transcript${data.transcripts_analyzed !== 1 ? 's' : ''}
                    </div>
                </div>`;
        } catch (e) {
            document.querySelector('.modal-body').innerHTML = `
                <div style="padding:var(--space-4);text-align:center">
                    <i class="fas fa-exclamation-circle" style="font-size:2rem;color:var(--danger)"></i>
                    <p class="mt-2">Failed to generate analysis. ${e.message || 'Please try again.'}</p>
                </div>`;
        }
    },

    async showRespondents(surveyId) {
        Helpers.openModal('Loading...', `
            <div style="padding:var(--space-4);text-align:center">
                <div class="spinner" style="margin:0 auto var(--space-3)"></div>
                <p class="text-muted">Loading respondent data and charts...</p>
            </div>
        `);
        try {
            const analytics = await API.publish.analytics(surveyId);
            const survey = this.surveys.find(s => s.id === surveyId);
            const respondents = analytics.respondents || [];
            const sentDist = analytics.sentiment_distribution || {};
            const totalSent = (sentDist.positive || 0) + (sentDist.neutral || 0) + (sentDist.negative || 0);
            const channelBreak = analytics.channel_breakdown || [];
            const emotionBreak = analytics.emotion_breakdown || [];
            const questionStats = analytics.question_stats || [];

            Helpers.openModal(`Respondents — ${survey?.title || 'Survey'}`, `
                <div style="padding:var(--space-3)">
                    <!-- Stats -->
                    <div class="grid grid-4 gap-2 mb-3">
                        <div class="card" style="text-align:center;padding:var(--space-2)">
                            <div style="font-size:1.5rem;font-weight:700;color:var(--primary-500)">${analytics.total_respondents}</div>
                            <div class="text-muted" style="font-size:0.75rem">Total</div>
                        </div>
                        <div class="card" style="text-align:center;padding:var(--space-2)">
                            <div style="font-size:1.5rem;font-weight:700;color:var(--success)">${analytics.completed}</div>
                            <div class="text-muted" style="font-size:0.75rem">Completed</div>
                        </div>
                        <div class="card" style="text-align:center;padding:var(--space-2)">
                            <div style="font-size:1.5rem;font-weight:700;color:var(--warning)">${analytics.completion_rate || 0}%</div>
                            <div class="text-muted" style="font-size:0.75rem">Rate</div>
                        </div>
                        <div class="card" style="text-align:center;padding:var(--space-2)">
                            <div style="font-size:1.5rem;font-weight:700;color:#7c3aed">${analytics.avg_sentiment != null ? (analytics.avg_sentiment * 100).toFixed(0) + '%' : '—'}</div>
                            <div class="text-muted" style="font-size:0.75rem">Sentiment</div>
                        </div>
                    </div>

                    <!-- Charts Row -->
                    <div class="grid grid-${totalSent > 0 && channelBreak.length > 0 ? '2' : '1'} gap-2 mb-3">
                        ${totalSent > 0 ? `
                            <div class="card" style="padding:var(--space-3)">
                                <h4 style="font-size:0.85rem;margin:0 0 var(--space-2) 0;color:var(--neutral-600)"><i class="fas fa-heart" style="color:var(--danger)"></i> Sentiment Distribution</h4>
                                <div style="height:180px;position:relative"><canvas id="chart-sentiment"></canvas></div>
                            </div>
                        ` : ''}
                        ${channelBreak.length > 0 ? `
                            <div class="card" style="padding:var(--space-3)">
                                <h4 style="font-size:0.85rem;margin:0 0 var(--space-2) 0;color:var(--neutral-600)"><i class="fas fa-tower-broadcast" style="color:var(--primary-500)"></i> Channel Breakdown</h4>
                                <div style="height:180px;position:relative"><canvas id="chart-channels"></canvas></div>
                            </div>
                        ` : ''}
                    </div>

                    ${emotionBreak.length > 0 ? `
                        <div class="card mb-3" style="padding:var(--space-3)">
                            <h4 style="font-size:0.85rem;margin:0 0 var(--space-2) 0;color:var(--neutral-600)"><i class="fas fa-face-grin-stars" style="color:var(--warning)"></i> Emotion Breakdown</h4>
                            <div style="height:200px;position:relative"><canvas id="chart-emotions"></canvas></div>
                        </div>
                    ` : ''}

                    ${questionStats.length > 0 ? `
                        <div class="card mb-3" style="padding:var(--space-3)">
                            <h4 style="font-size:0.85rem;margin:0 0 var(--space-2) 0;color:var(--neutral-600)"><i class="fas fa-chart-line" style="color:var(--success)"></i> Per-Question Sentiment</h4>
                            <div style="height:220px;position:relative"><canvas id="chart-question-sentiment"></canvas></div>
                        </div>
                    ` : ''}

                    <!-- Respondent Table -->
                    ${respondents.length > 0 ? `
                        <table style="width:100%;border-collapse:collapse;font-size:0.9rem">
                            <thead style="background:var(--neutral-50)">
                                <tr>
                                    <th style="padding:8px;text-align:left;border-bottom:2px solid var(--border)">Email</th>
                                    <th style="padding:8px;text-align:left;border-bottom:2px solid var(--border)">Channel</th>
                                    <th style="padding:8px;text-align:left;border-bottom:2px solid var(--border)">Status</th>
                                    <th style="padding:8px;text-align:right;border-bottom:2px solid var(--border)">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${respondents.map(r => `
                                    <tr style="border-bottom:1px solid var(--border)">
                                        <td style="padding:8px">${Helpers.escapeHtml(r.email || 'Anonymous')}</td>
                                        <td style="padding:8px">
                                            <span class="badge" style="font-size:0.75rem;padding:2px 8px">
                                                <i class="fas ${r.channel === 'chat' ? 'fa-comments' : r.channel === 'audio' ? 'fa-microphone' : 'fa-clipboard-list'}"></i>
                                                ${r.channel || '—'}
                                            </span>
                                        </td>
                                        <td style="padding:8px">
                                            <span style="color:${r.status === 'completed' ? 'var(--success)' : 'var(--warning)'}">
                                                <i class="fas ${r.status === 'completed' ? 'fa-check-circle' : 'fa-clock'}"></i> ${r.status || 'active'}
                                            </span>
                                        </td>
                                        <td style="padding:8px;text-align:right">
                                            ${r.session_id ? `
                                                <button class="btn btn-sm" style="font-size:0.75rem" onclick="MySurveys.viewTranscript('${r.session_id}')">
                                                    <i class="fas fa-file-alt"></i> Transcript
                                                </button>
                                            ` : '<span class="text-muted" style="font-size:0.8rem">No session</span>'}
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    ` : `
                        <div style="text-align:center;padding:var(--space-4)">
                            <i class="fas fa-user-slash" style="font-size:2rem;color:var(--neutral-400)"></i>
                            <p class="text-muted mt-2">No respondents yet. Share your survey link to start collecting responses.</p>
                        </div>
                    `}
                </div>
            `);

            // Render charts after modal DOM is ready
            setTimeout(() => this._renderCharts(sentDist, totalSent, channelBreak, emotionBreak, questionStats), 100);
        } catch (e) {
            Helpers.toast('Error', e.message || 'Failed to load respondents', 'error');
        }
    },

    _renderCharts(sentDist, totalSent, channelBreak, emotionBreak, questionStats) {
        const chartDefaults = { responsive: true, maintainAspectRatio: false };

        // ── Sentiment Doughnut ──
        const sentCtx = document.getElementById('chart-sentiment');
        if (sentCtx && totalSent > 0) {
            new Chart(sentCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Positive', 'Neutral', 'Negative'],
                    datasets: [{
                        data: [sentDist.positive || 0, sentDist.neutral || 0, sentDist.negative || 0],
                        backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                        borderWidth: 2, borderColor: '#fff',
                    }]
                },
                options: { ...chartDefaults, plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } } }
            });
        }

        // ── Channel Bar Chart ──
        const chanCtx = document.getElementById('chart-channels');
        if (chanCtx && channelBreak.length > 0) {
            const channelColors = { 'web-form': '#6366f1', chat: '#8b5cf6', audio: '#f59e0b', voice: '#f59e0b' };
            new Chart(chanCtx, {
                type: 'bar',
                data: {
                    labels: channelBreak.map(c => c.channel),
                    datasets: [{
                        label: 'Responses',
                        data: channelBreak.map(c => c.count),
                        backgroundColor: channelBreak.map(c => channelColors[c.channel] || '#6366f1'),
                        borderRadius: 6, barThickness: 40,
                    }]
                },
                options: {
                    ...chartDefaults,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { stepSize: 1, font: { size: 11 } } }, x: { ticks: { font: { size: 11 } } } }
                }
            });
        }

        // ── Emotion Polar Area ──
        const emoCtx = document.getElementById('chart-emotions');
        if (emoCtx && emotionBreak.length > 0) {
            const emoColors = ['#6366f1','#ec4899','#f59e0b','#10b981','#ef4444','#14b8a6','#8b5cf6','#f97316'];
            new Chart(emoCtx, {
                type: 'polarArea',
                data: {
                    labels: emotionBreak.map(e => e.emotion),
                    datasets: [{
                        data: emotionBreak.map(e => e.count),
                        backgroundColor: emotionBreak.map((_, i) => emoColors[i % emoColors.length] + 'cc'),
                        borderWidth: 1,
                    }]
                },
                options: { ...chartDefaults, plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } } }
            });
        }

        // ── Per-Question Sentiment Line ──
        const qCtx = document.getElementById('chart-question-sentiment');
        if (qCtx && questionStats.length > 0) {
            new Chart(qCtx, {
                type: 'line',
                data: {
                    labels: questionStats.map((q, i) => `Q${i + 1}`),
                    datasets: [
                        {
                            label: 'Avg Sentiment',
                            data: questionStats.map(q => q.avg_sentiment != null ? +(q.avg_sentiment).toFixed(2) : 0),
                            borderColor: '#6366f1', backgroundColor: '#6366f133',
                            fill: true, tension: 0.3, pointRadius: 4,
                        },
                        {
                            label: 'Avg Quality',
                            data: questionStats.map(q => q.avg_quality != null ? +(q.avg_quality).toFixed(2) : 0),
                            borderColor: '#10b981', backgroundColor: '#10b98133',
                            fill: true, tension: 0.3, pointRadius: 4,
                        }
                    ]
                },
                options: {
                    ...chartDefaults,
                    plugins: {
                        legend: { position: 'bottom', labels: { font: { size: 11 } } },
                        tooltip: {
                            callbacks: {
                                afterLabel(ctx) {
                                    const q = questionStats[ctx.dataIndex];
                                    return q?.question_text ? q.question_text.substring(0, 80) : '';
                                }
                            }
                        }
                    },
                    scales: { y: { ticks: { font: { size: 11 } } }, x: { ticks: { font: { size: 11 } } } }
                }
            });
        }
    },

    async viewTranscript(sessionId) {
        Helpers.openModal('Transcript', `
            <div style="padding:var(--space-4);text-align:center">
                <div class="spinner" style="margin:0 auto var(--space-3)"></div>
                <p class="text-muted">Loading transcript...</p>
            </div>
        `);
        try {
            // Try to get existing transcript first
            let transcript = null;
            try {
                transcript = await API.publish.getSessionTranscript(sessionId);
            } catch (e) {
                // No transcript yet — try generating one
                try {
                    await API.publish.saveTranscript(sessionId);
                    transcript = await API.publish.getSessionTranscript(sessionId);
                } catch (e2) {
                    throw new Error('No transcript data available');
                }
            }

            let entries = [];
            try { entries = JSON.parse(transcript.transcript_json || '[]'); } catch(e) { entries = []; }

            // If no conversation data, show a meaningful message
            if (entries.length === 0) {
                Helpers.openModal('Interview Transcript', `
                    <div style="padding:var(--space-4);text-align:center">
                        <i class="fas fa-comment-slash" style="font-size:2.5rem;color:var(--neutral-400);margin-bottom:var(--space-3)"></i>
                        <h3 style="color:var(--neutral-600)">No Conversation Data Yet</h3>
                        <p class="text-muted">This respondent hasn't completed their interview yet, or their session data is still being processed.</p>
                    </div>
                `);
                return;
            }

            // Parse AI report if available
            let aiReport = null;
            try { aiReport = transcript.ai_report_json ? JSON.parse(transcript.ai_report_json) : null; } catch(e) {}

            Helpers.openModal('Interview Transcript', `
                <div style="padding:var(--space-3)">
                    <!-- Stats bar -->
                    <div class="flex gap-3 mb-3" style="font-size:0.85rem;color:var(--neutral-500)">
                        <span><i class="fas fa-file-word"></i> ${transcript.word_count || 0} words</span>
                        <span><i class="fas fa-comments"></i> ${entries.length} messages</span>
                        ${transcript.sentiment_overall ? `<span><i class="fas fa-heart"></i> Sentiment: ${(transcript.sentiment_overall * 100).toFixed(0)}%</span>` : ''}
                    </div>

                    ${aiReport ? `
                    <!-- AI Analysis Summary -->
                    <div class="card mb-3" style="padding:var(--space-3);border-left:4px solid var(--primary-500);background:var(--primary-50,#f0f4ff)">
                        <h4 style="margin:0 0 var(--space-2) 0;color:var(--primary-600)"><i class="fas fa-brain"></i> AI Analysis</h4>
                        ${aiReport.executive_summary ? `<p style="font-size:0.9rem;line-height:1.6;margin-bottom:var(--space-2)">${Helpers.escapeHtml(aiReport.executive_summary)}</p>` : ''}
                        ${aiReport.overall_analysis ? `
                            <div class="grid grid-3 gap-2 mt-2">
                                <div style="text-align:center;padding:var(--space-2);background:white;border-radius:var(--radius-md)">
                                    <div style="font-size:0.75rem;color:var(--neutral-500)">Sentiment</div>
                                    <div style="font-weight:700;color:var(--primary-500)">${aiReport.overall_analysis.overall_sentiment || 'N/A'}</div>
                                </div>
                                <div style="text-align:center;padding:var(--space-2);background:white;border-radius:var(--radius-md)">
                                    <div style="font-size:0.75rem;color:var(--neutral-500)">Engagement</div>
                                    <div style="font-weight:700;color:var(--success)">${aiReport.overall_analysis.engagement_level || 'N/A'}</div>
                                </div>
                                <div style="text-align:center;padding:var(--space-2);background:white;border-radius:var(--radius-md)">
                                    <div style="font-size:0.75rem;color:var(--neutral-500)">Honesty</div>
                                    <div style="font-weight:700;color:#7c3aed">${aiReport.overall_analysis.honesty_assessment || 'N/A'}</div>
                                </div>
                            </div>
                        ` : ''}
                        ${aiReport.overall_analysis?.pain_points?.length > 0 ? `
                            <div style="margin-top:var(--space-2)">
                                <strong style="font-size:0.85rem"><i class="fas fa-exclamation-triangle" style="color:var(--warning)"></i> Pain Points:</strong>
                                <ul style="margin:var(--space-1) 0 0 var(--space-3);font-size:0.85rem">
                                    ${aiReport.overall_analysis.pain_points.map(p => `<li>${Helpers.escapeHtml(p)}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        ${aiReport.recommendations?.length > 0 ? `
                            <div style="margin-top:var(--space-2)">
                                <strong style="font-size:0.85rem"><i class="fas fa-lightbulb" style="color:var(--warning)"></i> Recommendations:</strong>
                                <ul style="margin:var(--space-1) 0 0 var(--space-3);font-size:0.85rem">
                                    ${aiReport.recommendations.map(r => `<li>${Helpers.escapeHtml(r)}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                    ` : ''}

                    <!-- Conversation -->
                    <h4 class="mb-2"><i class="fas fa-comments"></i> Conversation</h4>
                    <div style="max-height:400px;overflow-y:auto;padding:var(--space-2);background:var(--neutral-50);border-radius:var(--radius-md)">
                        ${entries.map(e => `
                            <div style="margin-bottom:var(--space-3);display:flex;flex-direction:${e.role === 'ai' ? 'row' : 'row-reverse'};gap:var(--space-2)">
                                <div style="width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;
                                    background:${e.role === 'ai' ? 'var(--primary-100)' : '#dcfce7'};color:${e.role === 'ai' ? 'var(--primary-600)' : 'var(--success)'}">
                                    <i class="fas ${e.role === 'ai' ? 'fa-robot' : 'fa-user'}"></i>
                                </div>
                                <div style="max-width:80%;padding:var(--space-2) var(--space-3);border-radius:var(--radius-lg);
                                    background:${e.role === 'ai' ? 'white' : 'var(--primary-500)'};color:${e.role === 'ai' ? 'inherit' : 'white'};
                                    box-shadow:0 1px 3px rgba(0,0,0,0.08)">
                                    <div style="font-size:0.9rem">${Helpers.escapeHtml(e.message)}</div>
                                    <div style="font-size:0.7rem;opacity:0.6;margin-top:4px">${e.timestamp || ''}</div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `);
        } catch (e) {
            Helpers.toast('Error', e.message || 'Transcript not available yet', 'warning');
        }
    },

    showExport(surveyId) {
        const survey = this.surveys.find(s => s.id === surveyId);
        Helpers.openModal(`Export Data — ${survey?.title || 'Survey'}`, `
            <div style="padding:var(--space-4)">
                <p class="text-muted mb-3">Download your survey data in different formats:</p>
                <div class="grid grid-1 gap-2">
                    <div class="card" style="padding:var(--space-3);border-left:4px solid var(--primary-500);cursor:pointer" onclick="MySurveys._doExport(${surveyId},'respondents')">
                        <div class="flex align-center gap-3">
                            <i class="fas fa-users fa-lg" style="color:var(--primary-500)"></i>
                            <div style="flex:1">
                                <strong>Respondents CSV</strong>
                                <p class="text-muted" style="font-size:0.8rem;margin:0">Email, channel, status, completion rate for all respondents</p>
                            </div>
                            <i class="fas fa-download" style="color:var(--primary-500)"></i>
                        </div>
                    </div>
                    <div class="card" style="padding:var(--space-3);border-left:4px solid var(--success);cursor:pointer" onclick="MySurveys._doExport(${surveyId},'analysis')">
                        <div class="flex align-center gap-3">
                            <i class="fas fa-chart-bar fa-lg" style="color:var(--success)"></i>
                            <div style="flex:1">
                                <strong>Responses CSV</strong>
                                <p class="text-muted" style="font-size:0.8rem;margin:0">All responses with sentiment, emotion, quality scores</p>
                            </div>
                            <i class="fas fa-download" style="color:var(--success)"></i>
                        </div>
                    </div>
                    <div class="card" style="padding:var(--space-3);border-left:4px solid #7c3aed;cursor:pointer" onclick="MySurveys._doExport(${surveyId},'report')">
                        <div class="flex align-center gap-3">
                            <i class="fas fa-file-pdf fa-lg" style="color:#7c3aed"></i>
                            <div style="flex:1">
                                <strong>Report (HTML/PDF)</strong>
                                <p class="text-muted" style="font-size:0.8rem;margin:0">Printable report with stats and respondent summary — use Print → Save as PDF</p>
                            </div>
                            <i class="fas fa-download" style="color:#7c3aed"></i>
                        </div>
                    </div>
                </div>
            </div>
        `);
    },

    async _doExport(surveyId, type) {
        try {
            Helpers.toast('Exporting...', 'Preparing your download', 'info', 2000);
            if (type === 'respondents') await API.publish.exportRespondentsCSV(surveyId);
            else if (type === 'analysis') await API.publish.exportAnalysisCSV(surveyId);
            else if (type === 'report') await API.publish.exportReportHTML(surveyId);
            Helpers.toast('Downloaded!', 'File saved to your downloads folder', 'success', 3000);
        } catch (e) {
            Helpers.toast('Export Failed', e.message || 'Could not export', 'error');
        }
    },

    showEmailInvite(surveyId) {
        const survey = this.surveys.find(s => s.id === surveyId);
        Helpers.openModal(`Email Invitations — ${survey?.title || 'Survey'}`, `
            <div style="padding:var(--space-4)">
                <p class="text-muted mb-3">Enter email addresses (one per line) to invite respondents:</p>
                <textarea id="invite-emails" rows="5" placeholder="alice@example.com&#10;bob@example.com&#10;charlie@example.com"
                    style="width:100%;padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-md);font-size:0.9rem;font-family:monospace;resize:vertical"></textarea>
                <p class="text-muted" style="font-size:0.75rem;margin-top:4px">Maximum 50 addresses. One per line or comma-separated.</p>
                <div class="flex gap-2 mt-3">
                    <button class="btn btn-primary" onclick="MySurveys._sendInvites(${surveyId})" style="flex:1">
                        <i class="fas fa-paper-plane"></i> Send Invitations
                    </button>
                </div>
                <div id="invite-result" class="mt-3" hidden></div>
            </div>
        `);
    },

    async _sendInvites(surveyId) {
        const textarea = document.getElementById('invite-emails');
        const resultDiv = document.getElementById('invite-result');
        if (!textarea) return;

        const raw = textarea.value.trim();
        if (!raw) {
            Helpers.toast('No emails', 'Please enter at least one email address.', 'warning');
            return;
        }

        // Parse emails — split by newline, comma, semicolon, or space
        const emails = raw.split(/[\\n,;\\s]+/).map(e => e.trim()).filter(e => e && e.includes('@'));
        if (emails.length === 0) {
            Helpers.toast('Invalid emails', 'No valid email addresses found.', 'warning');
            return;
        }
        if (emails.length > 50) {
            Helpers.toast('Too many', 'Maximum 50 addresses per batch.', 'warning');
            return;
        }

        try {
            Helpers.toast('Sending...', `Inviting ${emails.length} recipient(s)`, 'info', 3000);
            const result = await API.notifications.sendInvites(surveyId, emails);

            if (result.method === 'mailto') {
                // SMTP not configured — open mailto link
                if (resultDiv) {
                    resultDiv.hidden = false;
                    resultDiv.innerHTML = `
                        <div class="card" style="padding:var(--space-3);border-left:4px solid var(--warning);background:#fefce8">
                            <p style="font-size:0.85rem;margin:0 0 8px"><i class="fas fa-info-circle" style="color:var(--warning)"></i> <strong>SMTP not configured</strong> — opening your email client instead.</p>
                            <a href="${result.mailto_link}" class="btn btn-secondary btn-sm" target="_blank">
                                <i class="fas fa-external-link-alt"></i> Open Email Client
                            </a>
                        </div>
                    `;
                }
                // Also try opening directly
                window.open(result.mailto_link, '_blank');
            } else {
                // Real SMTP — show results
                const msg = `${result.sent} of ${result.total} invitation(s) sent successfully.`;
                Helpers.toast('Invitations Sent!', msg, result.failed > 0 ? 'warning' : 'success');
                if (resultDiv) {
                    resultDiv.hidden = false;
                    resultDiv.innerHTML = `
                        <div class="card" style="padding:var(--space-3);border-left:4px solid var(--success);background:#f0fdf4">
                            <p style="font-size:0.85rem;margin:0"><i class="fas fa-check-circle" style="color:var(--success)"></i> <strong>${msg}</strong></p>
                            ${result.failed > 0 ? `<p class="text-muted" style="font-size:0.8rem;margin:4px 0 0">${result.failed} failed — check email addresses.</p>` : ''}
                        </div>
                    `;
                }
                textarea.value = '';
            }
        } catch (e) {
            Helpers.toast('Failed', e.message || 'Could not send invitations', 'error');
        }
    },

    destroy() {}
};
