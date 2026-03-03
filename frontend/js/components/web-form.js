/**
 * Web Form Component — Conversational web-based survey form
 * Feature 2: Multi-Channel Collection (Web Form channel)
 */
const WebForm = {
    session: null,
    questions: [],
    currentIndex: 0,
    responses: [],
    surveyId: 1,

    async init() {
        this.render();
        await this.startSession();
    },

    render() {
        const page = document.getElementById('page-web-form');
        if (!page) return;
        page.innerHTML = `
            <div class="web-form-container">
                <div class="web-form-header">
                    <h2><i class="fas fa-clipboard-list"></i> Web Survey</h2>
                    <div class="progress-bar-container">
                        <div class="progress-bar" id="wf-progress" style="width:0%"></div>
                    </div>
                    <div class="progress-text text-muted" id="wf-progress-text">Loading...</div>
                </div>
                <div class="web-form-body" id="wf-body">
                    <div class="spinner"></div>
                </div>
                <div class="web-form-nav" id="wf-nav" hidden>
                    <button class="btn btn-secondary" id="wf-prev" disabled>
                        <i class="fas fa-arrow-left"></i> Previous
                    </button>
                    <div class="wf-auto-save text-muted" id="wf-autosave"></div>
                    <button class="btn btn-primary" id="wf-next">
                        Next <i class="fas fa-arrow-right"></i>
                    </button>
                </div>
            </div>
        `;
    },

    async startSession() {
        try {
            // Load survey questions
            const surveys = await API.surveys.list();
            if (surveys.length > 0) {
                this.surveyId = surveys[0].id;
                this.questions = await API.surveys.getQuestions(this.surveyId);
            }
            if (this.questions.length === 0) {
                // Fallback demo questions
                this.questions = [
                    { id: 1, question_text: 'How would you describe your overall experience with our product?', question_type: 'open_ended', is_required: true },
                    { id: 2, question_text: 'How likely are you to recommend us to others?', question_type: 'scale', is_required: true },
                    { id: 3, question_text: 'What features do you use most?', question_type: 'multiple_choice', is_required: false, options: ['Dashboard', 'Reports', 'Analytics', 'Settings'] },
                    { id: 4, question_text: 'Rate your satisfaction with customer support.', question_type: 'rating', is_required: true },
                    { id: 5, question_text: 'Would you like to be contacted for a follow-up?', question_type: 'yes_no', is_required: false },
                    { id: 6, question_text: 'Any additional feedback or suggestions?', question_type: 'open_ended', is_required: false }
                ];
            }

            // Create interview session
            this.session = await API.interviews.createSession({
                survey_id: this.surveyId,
                channel: 'web_form',
                respondent_id: 'web_user_' + Helpers.uid()
            });

            this.responses = new Array(this.questions.length).fill(null);
            document.getElementById('wf-nav').hidden = false;
            this.renderQuestion();
            this.bindNav();
        } catch (e) {
            console.error(e);
            document.getElementById('wf-body').innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-circle"></i><p>Failed to load survey. Please try again.</p></div>';
        }
    },

    bindNav() {
        document.getElementById('wf-prev')?.addEventListener('click', () => this.prevQuestion());
        document.getElementById('wf-next')?.addEventListener('click', () => this.nextQuestion());
    },

    renderQuestion() {
        const body = document.getElementById('wf-body');
        const q = this.questions[this.currentIndex];
        if (!q || !body) return;

        const pct = Math.round(((this.currentIndex) / this.questions.length) * 100);
        document.getElementById('wf-progress').style.width = pct + '%';
        document.getElementById('wf-progress-text').textContent = `Question ${this.currentIndex + 1} of ${this.questions.length}`;

        document.getElementById('wf-prev').disabled = this.currentIndex === 0;
        const nextBtn = document.getElementById('wf-next');
        nextBtn.innerHTML = this.currentIndex === this.questions.length - 1
            ? '<i class="fas fa-check"></i> Submit'
            : 'Next <i class="fas fa-arrow-right"></i>';

        const savedValue = this.responses[this.currentIndex] || '';

        body.innerHTML = `
            <div class="question-card-form stagger-children">
                <div class="question-label">
                    <span class="question-num">Q${this.currentIndex + 1}</span>
                    ${Helpers.escapeHtml(q.question_text)}
                    ${q.is_required ? '<span class="text-danger">*</span>' : ''}
                </div>
                <div class="question-input mt-2">
                    ${this.getInputHTML(q, savedValue)}
                </div>
            </div>
        `;

        // Auto-save on change
        body.querySelectorAll('input, textarea, select').forEach(el => {
            el.addEventListener('change', () => this.saveCurrentAnswer());
            el.addEventListener('input', Helpers.debounce(() => this.saveCurrentAnswer(), 500));
        });
    },

    getInputHTML(q, value) {
        switch (q.question_type) {
            case 'open_ended':
                return `<textarea id="wf-answer" rows="4" class="form-input" placeholder="Type your response...">${Helpers.escapeHtml(value)}</textarea>`;
            case 'rating':
                return `
                    <div class="star-rating-input" id="wf-answer">
                        ${[1,2,3,4,5].map(s => `
                            <button class="star-btn ${+value >= s ? 'active' : ''}" data-value="${s}" aria-label="${s} star">
                                <i class="fas fa-star"></i>
                            </button>
                        `).join('')}
                    </div>
                    <script>
                        document.querySelectorAll('.star-btn').forEach(btn => {
                            btn.addEventListener('click', () => {
                                document.querySelectorAll('.star-btn').forEach((b, i) => {
                                    b.classList.toggle('active', i < +btn.dataset.value);
                                });
                                btn.closest('.star-rating-input').dataset.value = btn.dataset.value;
                                // Trigger change
                                btn.dispatchEvent(new Event('change', {bubbles: true}));
                            });
                        });
                    </script>
                `;
            case 'scale':
                return `
                    <div class="scale-input">
                        <input type="range" id="wf-answer" min="1" max="10" value="${value || 5}" class="form-range">
                        <div class="flex justify-between text-muted"><span>1 - Not at all</span><span id="scale-val">${value || 5}</span><span>10 - Extremely</span></div>
                    </div>
                    <script>
                        document.getElementById('wf-answer')?.addEventListener('input', (e) => {
                            document.getElementById('scale-val').textContent = e.target.value;
                        });
                    </script>
                `;
            case 'yes_no':
                return `
                    <div class="yes-no-input flex gap-1" id="wf-answer">
                        <button class="btn ${value === 'Yes' ? 'btn-primary' : 'btn-secondary'} yn-btn" data-value="Yes">Yes</button>
                        <button class="btn ${value === 'No' ? 'btn-primary' : 'btn-secondary'} yn-btn" data-value="No">No</button>
                    </div>
                    <script>
                        document.querySelectorAll('.yn-btn').forEach(btn => {
                            btn.addEventListener('click', () => {
                                document.querySelectorAll('.yn-btn').forEach(b => b.className = 'btn btn-secondary yn-btn');
                                btn.className = 'btn btn-primary yn-btn';
                                btn.closest('.yes-no-input').dataset.value = btn.dataset.value;
                                btn.dispatchEvent(new Event('change', {bubbles: true}));
                            });
                        });
                    </script>
                `;
            case 'multiple_choice':
                const options = q.options || ['Option A', 'Option B', 'Option C'];
                return `
                    <div class="mc-options" id="wf-answer">
                        ${options.map(o => `
                            <label class="mc-option ${value === o ? 'selected' : ''}">
                                <input type="radio" name="mc" value="${Helpers.escapeHtml(o)}" ${value === o ? 'checked' : ''}>
                                ${Helpers.escapeHtml(o)}
                            </label>
                        `).join('')}
                    </div>
                `;
            default:
                return `<textarea id="wf-answer" rows="4" class="form-input" placeholder="Type your response...">${Helpers.escapeHtml(value)}</textarea>`;
        }
    },

    saveCurrentAnswer() {
        const q = this.questions[this.currentIndex];
        let value = '';

        if (q.question_type === 'rating') {
            const ratingEl = document.querySelector('.star-rating-input');
            value = ratingEl?.dataset.value || '';
        } else if (q.question_type === 'yes_no') {
            const ynEl = document.querySelector('.yes-no-input');
            value = ynEl?.dataset.value || '';
        } else if (q.question_type === 'multiple_choice') {
            const checked = document.querySelector('.mc-options input:checked');
            value = checked?.value || '';
        } else {
            const el = document.getElementById('wf-answer');
            value = el?.value || '';
        }

        this.responses[this.currentIndex] = value;

        // Show auto-save indicator
        const indicator = document.getElementById('wf-autosave');
        if (indicator) {
            indicator.textContent = '✓ Saved';
            setTimeout(() => indicator.textContent = '', 2000);
        }
    },

    async nextQuestion() {
        this.saveCurrentAnswer();

        const q = this.questions[this.currentIndex];
        const value = this.responses[this.currentIndex];

        // Validation
        if (q.is_required && (!value || value.trim() === '')) {
            Helpers.toast('Required', 'Please answer this question before continuing.', 'warning');
            return;
        }

        // Submit response to API
        if (this.session && value) {
            try {
                await API.interviews.respond({
                    session_id: this.session.session_id,
                    question_id: q.id,
                    response_text: String(value),
                    response_type: q.question_type
                });
            } catch (e) { console.error('Failed to submit response:', e); }
        }

        if (this.currentIndex < this.questions.length - 1) {
            this.currentIndex++;
            this.renderQuestion();
        } else {
            this.showCompletion();
        }
    },

    prevQuestion() {
        this.saveCurrentAnswer();
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.renderQuestion();
        }
    },

    showCompletion() {
        const body = document.getElementById('wf-body');
        const nav = document.getElementById('wf-nav');
        if (nav) nav.hidden = true;

        document.getElementById('wf-progress').style.width = '100%';
        document.getElementById('wf-progress-text').textContent = 'Complete!';

        body.innerHTML = `
            <div class="completion-state stagger-children" style="text-align:center; padding: var(--space-6)">
                <div style="font-size:4rem; color: var(--success); margin-bottom: var(--space-3)">
                    <i class="fas fa-check-circle"></i>
                </div>
                <h2>Thank You!</h2>
                <p class="text-muted mt-1">Your responses have been recorded successfully.</p>
                <p class="text-muted">Generating your transcript and report...</p>
                <div class="typing-indicator mt-2" style="display:inline-flex"><span></span><span></span><span></span></div>
                <div id="wf-report-container" class="mt-3" style="text-align:left"></div>
            </div>
        `;

        // Generate transcript report
        this.generateReport();
    },

    async generateReport() {
        const reportContainer = document.getElementById('wf-report-container');
        try {
            const result = await API.interviews.completeInterview(this.session.session_id);
            const report = result.report || {};

            // Remove typing indicator
            const typing = document.querySelector('.completion-state .typing-indicator');
            if (typing) typing.remove();
            const genMsg = document.querySelector('.completion-state p:last-of-type');

            if (reportContainer) {
                reportContainer.innerHTML = this.buildReportHTML(report);
            }
        } catch (e) {
            console.error('Report generation failed:', e);
            if (reportContainer) {
                reportContainer.innerHTML = `
                    <div class="card" style="border-left:4px solid var(--success); padding: var(--space-4)">
                        <p><i class="fas fa-check-circle" style="color:var(--success)"></i> All responses recorded. View the full report in the <strong>Reports</strong> section.</p>
                    </div>
                `;
            }
        }
    },

    buildReportHTML(report) {
        const ts = report.transcript_summary || {};
        const analysis = report.overall_analysis || {};
        const qSummaries = report.question_summaries || [];
        const recommendations = report.recommendations || [];
        const execSummary = report.executive_summary || '';

        let html = `
            <div class="card" style="overflow:hidden; border: 1px solid var(--border-light)">
                <div style="padding: var(--space-4); background: linear-gradient(135deg, var(--primary-500), var(--primary-700)); color: white;">
                    <h3 style="color:white; margin-bottom: 4px"><i class="fas fa-file-alt"></i> Interview Transcript & Report</h3>
                    <p style="opacity: 0.85; font-size: 0.85rem">${ts.total_questions_asked || 0} questions · ${ts.total_responses || 0} responses · ${ts.duration_estimate || 'N/A'}</p>
                </div>
        `;

        if (execSummary) {
            html += `
                <div style="padding: var(--space-4); border-bottom: 1px solid var(--border-light)">
                    <h4 style="margin-bottom: var(--space-2)"><i class="fas fa-align-left" style="color:var(--primary-500)"></i> Executive Summary</h4>
                    <p style="line-height:1.7; color: var(--text-secondary)">${Helpers.escapeHtml(execSummary)}</p>
                </div>
            `;
        }

        if (qSummaries.length > 0) {
            html += `<div style="padding: var(--space-4); border-bottom: 1px solid var(--border-light)">`;
            html += `<h4 style="margin-bottom: var(--space-3)"><i class="fas fa-clipboard-list" style="color:var(--primary-500)"></i> Question-by-Question Summary</h4>`;
            qSummaries.forEach((qs, i) => {
                const sentColor = qs.sentiment === 'positive' ? 'var(--success)' : qs.sentiment === 'negative' ? 'var(--danger)' : 'var(--warning)';
                html += `
                    <div style="margin-bottom: var(--space-3); padding: var(--space-3); background: var(--bg-secondary); border-radius: var(--radius-md); border-left: 3px solid ${sentColor}">
                        <p style="font-weight:600; font-size:0.9rem; margin-bottom: 4px">Q${i + 1}: ${Helpers.escapeHtml(qs.question || '')}</p>
                        <p style="color: var(--text-secondary); font-size:0.85rem">${Helpers.escapeHtml(qs.response_summary || '')}</p>
                        ${qs.key_insight ? `<p style="font-size:0.8rem; color: var(--primary-500); margin-top: 4px"><i class="fas fa-lightbulb"></i> ${Helpers.escapeHtml(qs.key_insight)}</p>` : ''}
                    </div>
                `;
            });
            html += `</div>`;
        }

        if (analysis.main_pain_points?.length || analysis.positive_highlights?.length || analysis.suggestions_made?.length) {
            html += `<div style="padding: var(--space-4); border-bottom: 1px solid var(--border-light)">`;
            html += `<h4 style="margin-bottom: var(--space-3)"><i class="fas fa-chart-pie" style="color:var(--primary-500)"></i> Analysis</h4>`;

            if (analysis.respondent_sentiment) {
                html += `<p style="margin-bottom: var(--space-2)"><strong>Overall Sentiment:</strong> ${Helpers.escapeHtml(analysis.respondent_sentiment)}</p>`;
            }

            const sections = [
                { items: analysis.main_pain_points, icon: 'fa-exclamation-triangle', color: 'var(--danger)', title: 'Pain Points' },
                { items: analysis.positive_highlights, icon: 'fa-thumbs-up', color: 'var(--success)', title: 'Positive Highlights' },
                { items: analysis.suggestions_made, icon: 'fa-lightbulb', color: 'var(--warning)', title: 'Suggestions' }
            ];

            sections.forEach(sec => {
                if (sec.items?.length > 0) {
                    html += `<div style="margin-bottom: var(--space-2)"><strong style="color:${sec.color}"><i class="fas ${sec.icon}"></i> ${sec.title}:</strong>`;
                    html += `<ul style="margin: 4px 0 0 var(--space-4); font-size:0.9rem">`;
                    sec.items.forEach(item => { html += `<li style="padding:2px 0">${Helpers.escapeHtml(item)}</li>`; });
                    html += `</ul></div>`;
                }
            });
            html += `</div>`;
        }

        if (recommendations.length > 0) {
            html += `<div style="padding: var(--space-4)">`;
            html += `<h4 style="margin-bottom: var(--space-3)"><i class="fas fa-tasks" style="color:var(--primary-500)"></i> Recommendations</h4>`;
            recommendations.forEach(rec => {
                const prioColor = rec.priority === 'high' ? 'var(--danger)' : rec.priority === 'medium' ? 'var(--warning)' : 'var(--success)';
                html += `
                    <div style="display:flex; align-items:start; gap: var(--space-2); margin-bottom: var(--space-2)">
                        <span style="background:${prioColor}; color:white; padding:2px 8px; border-radius: 12px; font-size:0.7rem; font-weight:600; text-transform:uppercase; flex-shrink:0; margin-top:2px">${rec.priority || 'medium'}</span>
                        <div>
                            <strong style="font-size:0.9rem">${Helpers.escapeHtml(rec.title || '')}</strong>
                            <p style="font-size:0.85rem; color: var(--text-secondary)">${Helpers.escapeHtml(rec.description || '')}</p>
                        </div>
                    </div>
                `;
            });
            html += `</div>`;
        }

        html += `</div>`;

        html += `
            <div class="mt-3" style="text-align:center">
                <button class="btn btn-primary" onclick="WebForm.restart()">
                    <i class="fas fa-redo"></i> Take Another Survey
                </button>
            </div>
        `;

        return html;
    },

    restart() {
        this.currentIndex = 0;
        this.responses = [];
        this.session = null;
        this.init();
    },

    destroy() {}
};
