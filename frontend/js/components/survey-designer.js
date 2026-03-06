/**
 * Survey Designer Component — AI-Powered Survey Creation Wizard
 * Redesigned: Deep AI analysis, questions with follow-ups, respondent briefing
 */
const SurveyDesigner = {
    currentStep: 0,
    steps: ['intake', 'review', 'briefing', 'launch'],
    survey: null,
    goalText: '',
    aiParsed: null,
    deepResult: null,
    questions: [],
    intakeConversation: [],   // Track the multi-step intake conversation
    intakeReady: false,       // Whether AI has enough info to generate questions

    async init() {
        this.currentStep = 0;
        this.survey = null;
        this.goalText = '';
        this.aiParsed = null;
        this.deepResult = null;
        this.questions = [];
        this.intakeConversation = [];
        this.intakeReady = false;
        this.targetAudiences = [];      // List of audience names
        this.audienceResult = null;     // Full audience-targeted AI result
        this.audienceSets = [];         // Array of {audience, questions, briefing}
        this.genericSet = null;         // Generic set for all audiences
        this.activeAudienceTab = 'generic'; // Currently viewed tab
        this.surveyTitle = '';           // User-defined survey title
        this.interviewDuration = 15;     // Interview duration in minutes
        this.interviewStyle = 'balanced'; // deep | balanced | fast
        this.includeConsent = false;     // Whether to include consent form
        this.consentFormText = '';       // AI-generated consent form HTML
        this.render();
        this.bindEvents();
    },

    render() {
        const page = document.getElementById('page-survey-designer');
        if (!page) return;
        page.innerHTML = `
            <div class="survey-designer">
                <!-- Wizard Steps -->
                <div class="wizard-steps">
                    <div class="wizard-step active" data-step="0">
                        <div class="wizard-step-number">1</div>
                        <span>Describe Your Survey</span>
                    </div>
                    <div class="wizard-step" data-step="1">
                        <div class="wizard-step-number">2</div>
                        <span>Review Questions</span>
                    </div>
                    <div class="wizard-step" data-step="2">
                        <div class="wizard-step-number">3</div>
                        <span>Interview Briefing</span>
                    </div>
                    <div class="wizard-step" data-step="3">
                        <div class="wizard-step-number">4</div>
                        <span>Launch</span>
                    </div>
                </div>

                <!-- Step Panels -->
                <div class="wizard-content">

                    <!-- STEP 0: Intake — Conversational AI Research Intake -->
                    <div class="wizard-panel active" id="step-intake">
                        <!-- Survey Title & Options -->
                        <div class="card mb-3" style="border-left: 4px solid var(--primary-500)">
                            <div class="card-body" style="padding: var(--space-4)">
                                <h3 style="margin-bottom: var(--space-3)"><i class="fas fa-heading" style="color:var(--primary-500)"></i> Survey Setup</h3>
                                <div class="form-group mb-2">
                                    <label for="survey-title-input" style="font-weight:600">Survey Title <span style="color:var(--danger)">*</span></label>
                                    <input type="text" id="survey-title-input" placeholder="e.g. DYHE Course Experience Survey" style="width:100%;padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-md);font-size:1rem" maxlength="120">
                                    <p class="text-muted" style="font-size:0.8rem;margin-top:4px">This title will be shown to respondents at the top of the interview.</p>
                                </div>
                                <div class="form-group mb-2" style="margin-top:var(--space-3)">
                                    <label for="duration-input" style="font-weight:600"><i class="fas fa-clock" style="color:var(--primary-500)"></i> Interview Duration (minutes)</label>
                                    <div style="display:flex;align-items:center;gap:12px">
                                        <input type="range" id="duration-slider" min="5" max="60" value="15" step="5" style="flex:1;accent-color:var(--primary-500)">
                                        <span id="duration-value" style="font-weight:700;font-size:1.1rem;color:var(--primary-500);min-width:60px;text-align:center">15 min</span>
                                    </div>
                                    <p class="text-muted" style="font-size:0.8rem;margin-top:4px">The AI interviewer will dynamically adjust questions to fit within this time. It may go ~1 minute over or under.</p>
                                </div>
                                <div class="form-group mb-2" style="margin-top:var(--space-3)">
                                    <label for="interview-style" style="font-weight:600"><i class="fas fa-sliders" style="color:var(--primary-500)"></i> Interview Style</label>
                                    <select id="interview-style" style="width:100%;padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-md);font-size:0.95rem">
                                        <option value="deep">Deep - ask more probing follow-ups</option>
                                        <option value="balanced" selected>Balanced - depth with time control</option>
                                        <option value="fast">Fast - fewer follow-ups, quicker pace</option>
                                    </select>
                                    <p class="text-muted" style="font-size:0.8rem;margin-top:4px">Choose how aggressively the AI probes for detail.</p>
                                </div>
                                <div style="display:flex;align-items:center;gap:12px;margin-top:var(--space-3);padding:12px 16px;background:var(--bg-secondary);border-radius:var(--radius-md)">
                                    <label class="switch" style="position:relative;display:inline-block;width:44px;height:24px;flex-shrink:0">
                                        <input type="checkbox" id="consent-toggle" style="opacity:0;width:0;height:0">
                                        <span style="position:absolute;cursor:pointer;inset:0;background:var(--gray-300);border-radius:24px;transition:.3s" class="consent-slider"></span>
                                    </label>
                                    <div>
                                        <strong style="font-size:0.95rem"><i class="fas fa-file-signature" style="color:var(--primary-500)"></i> Include Consent Form</strong>
                                        <p class="text-muted" style="font-size:0.8rem;margin:0">AI will generate a consent form that respondents must agree to before the interview.</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="ai-intake-conversation">
                            <div class="ai-message-row">
                                <div class="ai-avatar"><i class="fas fa-robot"></i></div>
                                <div class="ai-bubble">
                                    <p><strong>Hi! I'm your AI research assistant.</strong></p>
                                    <p>Tell me what you want to learn from your respondents, or <strong>pick a template</strong> to get started quickly.</p>
                                </div>
                            </div>

                            <!-- Template Picker -->
                            <div id="template-picker" style="margin:var(--space-3) 0">
                                <div style="display:flex;align-items:center;gap:8px;margin-bottom:var(--space-2)">
                                    <i class="fas fa-wand-magic-sparkles" style="color:var(--primary-500)"></i>
                                    <strong style="font-size:0.9rem">Quick Start Templates</strong>
                                    <span class="text-muted" style="font-size:0.8rem">— or describe your own below</span>
                                </div>
                                <div id="template-cards" class="grid grid-3 gap-2" style="margin-bottom:var(--space-2)">
                                    <div style="text-align:center;padding:var(--space-4)"><div class="spinner" style="margin:0 auto"></div></div>
                                </div>
                            </div>

                            <div id="ai-conversation-history"></div>
                            <div class="ai-intake-input">
                                <textarea id="goal-input" placeholder="Describe what you want to learn..." rows="3"></textarea>
                                <button class="btn btn-primary" id="btn-analyze-goal">
                                    <i class="fas fa-paper-plane"></i> Send
                                </button>
                            </div>
                        </div>
                        <div id="ai-loading-state" class="mt-3" hidden>
                            <div style="text-align:center; padding: var(--space-6)">
                                <div class="typing-indicator" style="display:inline-flex; margin-bottom: var(--space-3)"><span></span><span></span><span></span></div>
                                <p class="text-muted" id="ai-loading-text">AI is thinking...</p>
                            </div>
                        </div>
                    </div>

                    <!-- STEP 1: Review Questions with Follow-ups -->
                    <div class="wizard-panel" id="step-review">
                        <div id="ai-analysis-card" class="card mb-3">
                            <div class="card-header" style="background: linear-gradient(135deg, var(--primary-500), var(--primary-700)); color: white; border-radius: var(--radius-lg) var(--radius-lg) 0 0;">
                                <h3 style="color:white"><i class="fas fa-brain"></i> AI Analysis</h3>
                            </div>
                            <div id="ai-analysis-body" class="card-body"></div>
                        </div>

                        <div class="flex justify-between align-center mb-2">
                            <h2><i class="fas fa-list-check"></i> Generated Questions & Follow-ups</h2>
                            <div class="flex gap-1">
                                <button class="btn btn-secondary btn-sm" id="btn-regenerate">
                                    <i class="fas fa-sync"></i> Regenerate
                                </button>
                            </div>
                        </div>
                        <p class="text-muted mb-2">Review the questions below. Each main question has follow-up questions that will be asked based on the respondent's answers.</p>
                        <div id="deep-question-list"></div>

                        <div class="quality-score-ring mt-3" id="quality-score-container">
                            <div class="quality-ring">
                                <svg viewBox="0 0 100 100">
                                    <circle cx="50" cy="50" r="45" fill="none" stroke="var(--neutral-200)" stroke-width="8"/>
                                    <circle id="quality-ring-circle" cx="50" cy="50" r="45" fill="none" stroke="var(--primary-500)" stroke-width="8"
                                        stroke-dasharray="283" stroke-dashoffset="283" stroke-linecap="round" transform="rotate(-90 50 50)"/>
                                </svg>
                                <div class="quality-ring-value" id="quality-ring-value">0</div>
                            </div>
                            <div class="quality-ring-label">Survey Quality Score</div>
                        </div>
                    </div>

                    <!-- STEP 2: Briefing — What respondent will experience -->
                    <div class="wizard-panel" id="step-briefing">
                        <div class="card mb-3" style="border-left: 4px solid var(--primary-500)">
                            <div class="card-body" style="padding: var(--space-5)">
                                <h2 style="margin-bottom: var(--space-3)"><i class="fas fa-info-circle" style="color:var(--primary-500)"></i> Interview Briefing</h2>
                                <p class="text-muted mb-2">Here's what your respondents will experience during the interview:</p>
                                <div id="briefing-content"></div>
                            </div>
                        </div>

                        <div class="card mb-3">
                            <div class="card-header">
                                <h3><i class="fas fa-route"></i> Interview Flow</h3>
                            </div>
                            <div class="card-body">
                                <div id="flow-summary"></div>
                            </div>
                        </div>

                        <div class="card mb-3">
                            <div class="card-header">
                                <h3><i class="fas fa-list-ol"></i> Questions Preview</h3>
                            </div>
                            <div class="card-body" id="briefing-questions-preview"></div>
                        </div>

                        <div class="card" style="border-left: 4px solid var(--success)">
                            <div class="card-body" style="padding: var(--space-4)">
                                <h3><i class="fas fa-clipboard-check" style="color:var(--success)"></i> After the Interview</h3>
                                <p class="text-muted mt-1">When the respondent completes the interview, we will automatically:</p>
                                <ul class="mt-1" style="list-style: none; padding: 0;">
                                    <li style="padding: 6px 0;"><i class="fas fa-check-circle" style="color:var(--success); margin-right: 8px;"></i> Generate a complete transcript of every question and answer</li>
                                    <li style="padding: 6px 0;"><i class="fas fa-check-circle" style="color:var(--success); margin-right: 8px;"></i> Create per-question summaries with sentiment analysis</li>
                                    <li style="padding: 6px 0;"><i class="fas fa-check-circle" style="color:var(--success); margin-right: 8px;"></i> Identify key pain points and positive highlights</li>
                                    <li style="padding: 6px 0;"><i class="fas fa-check-circle" style="color:var(--success); margin-right: 8px;"></i> Generate an executive summary report</li>
                                    <li style="padding: 6px 0;"><i class="fas fa-check-circle" style="color:var(--success); margin-right: 8px;"></i> Provide actionable recommendations</li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <!-- STEP 3: Launch -->
                    <div class="wizard-panel" id="step-launch">
                        <div style="text-align:center; padding: var(--space-6)">
                            <div style="font-size:4rem; color: var(--success); margin-bottom: var(--space-3)">
                                <i class="fas fa-rocket"></i>
                            </div>
                            <h2>Your Survey is Ready!</h2>
                            <p class="text-muted mt-1 mb-3">Choose how you'd like to collect responses:</p>
                            <div class="grid grid-3 gap-2 mt-3" id="launch-channels">
                                <div class="card channel-launch-card" data-channel="web-form" style="cursor:pointer; text-align:center; padding: var(--space-4); transition: all 0.2s">
                                    <i class="fas fa-clipboard-list" style="font-size:2.5rem; color:var(--primary-500); margin-bottom: var(--space-2)"></i>
                                    <h3>Web Form</h3>
                                    <p class="text-muted" style="font-size:0.85rem">Progressive, conversational survey</p>
                                </div>
                                <div class="card channel-launch-card" data-channel="chat" style="cursor:pointer; text-align:center; padding: var(--space-4); transition: all 0.2s">
                                    <i class="fas fa-comments" style="font-size:2.5rem; color:var(--secondary-500, #8b5cf6); margin-bottom: var(--space-2)"></i>
                                    <h3>Chat Interview</h3>
                                    <p class="text-muted" style="font-size:0.85rem">WhatsApp-style AI conversation</p>
                                </div>
                                <div class="card channel-launch-card" data-channel="voice" style="cursor:pointer; text-align:center; padding: var(--space-4); transition: all 0.2s">
                                    <i class="fas fa-microphone" style="font-size:2.5rem; color:var(--warning); margin-bottom: var(--space-2)"></i>
                                    <h3>Voice Input</h3>
                                    <p class="text-muted" style="font-size:0.85rem">Speak naturally, AI transcribes</p>
                                </div>
                            </div>
                            <div id="launch-status" class="mt-3" hidden>
                                <div class="card" style="border-left: 4px solid var(--success); text-align:left; padding: var(--space-4)">
                                    <p><i class="fas fa-check-circle" style="color:var(--success)"></i> <strong>Survey launched!</strong></p>
                                    <p class="text-muted mt-1" id="launch-status-text"></p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Navigation -->
                <div class="wizard-nav flex justify-between mt-2">
                    <button class="btn btn-secondary" id="btn-prev-step" hidden>
                        <i class="fas fa-arrow-left"></i> Back
                    </button>
                    <div></div>
                    <button class="btn btn-primary" id="btn-next-step" hidden>
                        Next <i class="fas fa-arrow-right"></i>
                    </button>
                </div>
            </div>
        `;
    },

    bindEvents() {
        // Goal analysis
        document.getElementById('btn-analyze-goal')?.addEventListener('click', () => this.analyzeGoal());
        document.getElementById('btn-send-goal')?.addEventListener('click', () => this.analyzeGoal());

        // Duration slider
        const durationSlider = document.getElementById('duration-slider');
        if (durationSlider) {
            durationSlider.addEventListener('input', () => {
                this.interviewDuration = parseInt(durationSlider.value);
                document.getElementById('duration-value').textContent = this.interviewDuration + ' min';
            });
        }
        const styleSelect = document.getElementById('interview-style');
        if (styleSelect) {
            styleSelect.addEventListener('change', () => {
                this.interviewStyle = styleSelect.value || 'balanced';
            });
        }

        // Navigation
        document.getElementById('btn-prev-step')?.addEventListener('click', () => this.goStep(this.currentStep - 1));
        document.getElementById('btn-next-step')?.addEventListener('click', () => this.goStep(this.currentStep + 1));

        // Regenerate
        document.getElementById('btn-regenerate')?.addEventListener('click', () => this.analyzeGoal());

        // Goal textarea — Shift+Enter for newline, Ctrl+Enter to submit
        document.getElementById('goal-input')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault();
                this.analyzeGoal();
            }
        });

        // Launch channel cards
        document.querySelectorAll('.channel-launch-card').forEach(card => {
            card.addEventListener('click', () => this.launchSurvey(card.dataset.channel));
        });

        // Load templates
        this.loadTemplates();
    },

    async loadTemplates() {
        try {
            const templates = await API.surveys.getTemplates();
            const container = document.getElementById('template-cards');
            if (!container) return;
            container.innerHTML = templates.map(t => `
                <div class="card template-pick-card" style="cursor:pointer;padding:var(--space-3);text-align:center;transition:all .2s;border:2px solid transparent"
                     onclick="SurveyDesigner.applyTemplate('${t.id}')"
                     onmouseenter="this.style.borderColor='${t.color}';this.style.transform='translateY(-2px)'"
                     onmouseleave="this.style.borderColor='transparent';this.style.transform=''"
                     data-template-id="${t.id}">
                    <i class="fas ${t.icon}" style="font-size:1.8rem;color:${t.color};margin-bottom:8px"></i>
                    <div style="font-weight:600;font-size:0.9rem;margin-bottom:4px">${t.title}</div>
                    <div class="text-muted" style="font-size:0.75rem;line-height:1.3">${t.description.substring(0, 80)}…</div>
                    <span class="badge" style="margin-top:6px;font-size:0.7rem;padding:2px 8px;background:${t.color}22;color:${t.color}">${t.category}</span>
                </div>
            `).join('');
            this._templates = templates;
        } catch (e) {
            const container = document.getElementById('template-cards');
            if (container) container.innerHTML = '<p class="text-muted" style="font-size:0.85rem">Could not load templates — describe your survey below.</p>';
        }
    },

    applyTemplate(templateId) {
        const t = (this._templates || []).find(tpl => tpl.id === templateId);
        if (!t) return;
        // Pre-fill title
        const titleInput = document.getElementById('survey-title-input');
        if (titleInput && !titleInput.value.trim()) {
            titleInput.value = t.title;
        }
        // Pre-fill goal input
        const goalInput = document.getElementById('goal-input');
        if (goalInput) {
            goalInput.value = t.goal_text;
            goalInput.focus();
        }
        // Highlight selected card
        document.querySelectorAll('.template-pick-card').forEach(card => {
            card.style.borderColor = card.dataset.templateId === templateId ? t.color : 'transparent';
        });
        // Show toast
        Helpers.toast('Template Applied', `"${t.title}" loaded — click Send or customise the description.`, 'success', 3000);
    },

    async analyzeGoal() {
        // Prevent double submission
        if (this._isProcessing) return;

        const input = document.getElementById('goal-input');
        const text = input?.value.trim();
        if (!text) {
            Helpers.toast('Input needed', 'Please describe your research goal first.', 'warning');
            return;
        }

        this._isProcessing = true;
        const sendBtn = document.getElementById('btn-send-goal');
        if (sendBtn) { sendBtn.disabled = true; sendBtn.style.opacity = '0.6'; }

        // On first message, require a title
        const titleInput = document.getElementById('survey-title-input');
        if (titleInput && !this.surveyTitle) {
            const title = titleInput.value.trim();
            if (!title) {
                Helpers.toast('Title Required', 'Please enter a survey title before proceeding.', 'warning');
                titleInput.focus();
                titleInput.style.borderColor = 'var(--danger)';
                setTimeout(() => titleInput.style.borderColor = '', 2000);
                return;
            }
            this.surveyTitle = title;
            // Lock the title input
            titleInput.disabled = true;
            titleInput.style.opacity = '0.7';
        }

        // Capture consent toggle state
        const consentToggle = document.getElementById('consent-toggle');
        if (consentToggle) this.includeConsent = consentToggle.checked;

        // Accumulate goal text from the entire conversation
        if (!this.goalText) {
            this.goalText = text;
        } else {
            this.goalText += '\n' + text;
        }

        // Show user message in conversation
        const history = document.getElementById('ai-conversation-history');
        if (history) {
            history.innerHTML += `
                <div class="user-message-row">
                    <div class="user-bubble">${Helpers.escapeHtml(text)}</div>
                </div>
            `;
        }
        if (input) input.value = '';

        // Add to intake conversation tracking
        this.intakeConversation.push({ role: 'user', message: text });

        // Show loading
        const loadingEl = document.getElementById('ai-loading-state');
        if (loadingEl) loadingEl.hidden = false;
        const loadingTextEl = document.getElementById('ai-loading-text');
        if (loadingTextEl) loadingTextEl.textContent = 'AI is thinking...';

        try {
            // Step 1: Ask AI if it has enough information
            const clarification = await API.surveys.intakeClarify(text, this.intakeConversation);

            if (loadingEl) loadingEl.hidden = true;

            if (!clarification.has_enough_info) {
                // AI needs more info — show its question and wait for the user's answer
                this.intakeConversation.push({ role: 'ai', message: clarification.ai_message });

                if (history) {
                    history.innerHTML += `
                        <div class="ai-message-row">
                            <div class="ai-avatar"><i class="fas fa-robot"></i></div>
                            <div class="ai-bubble">${Helpers.escapeHtml(clarification.ai_message)}</div>
                        </div>
                    `;
                }
                // Scroll to bottom
                history?.scrollIntoView({ behavior: 'smooth', block: 'end' });
                input?.focus();
                return; // Wait for user's next message
            }

            // AI has enough info — proceed to generate questions
            this.intakeReady = true;

            // Extract target audiences from the AI's context analysis
            const extractedCtx = clarification.extracted_context || {};
            this.targetAudiences = extractedCtx.target_audiences || [];
            if (this.targetAudiences.length === 0 && extractedCtx.audience) {
                // Fallback: split comma-separated audience string
                this.targetAudiences = extractedCtx.audience.split(',').map(a => a.trim()).filter(Boolean);
            }

            // Show "generating" message
            if (history) {
                history.innerHTML += `
                    <div class="ai-message-row">
                        <div class="ai-avatar"><i class="fas fa-robot"></i></div>
                        <div class="ai-bubble">${Helpers.escapeHtml(clarification.ai_message)}</div>
                    </div>
                `;
            }

            if (loadingEl) loadingEl.hidden = false;
            const loadingTexts = this.targetAudiences.length > 1 ? [
                'Generating audience-specific questions for each target group...',
                `Creating tailored questions for ${this.targetAudiences.length} audiences...`,
                'Building follow-up questions for each audience segment...',
                'Generating generic survey for all audiences...',
                'Crafting respondent briefings...',
                'Almost done — polishing the survey design...'
            ] : [
                'Generating targeted questions based on our conversation...',
                'Identifying key research areas and themes...',
                'Creating follow-up questions for each main question...',
                'Crafting respondent briefing...',
                'Almost done — polishing the survey design...'
            ];
            let loadingIdx = 0;
            const loadingInterval = setInterval(() => {
                loadingIdx = (loadingIdx + 1) % loadingTexts.length;
                if (loadingTextEl) loadingTextEl.textContent = loadingTexts[loadingIdx];
            }, 2500);

            // Parse the full goal text
            const parsed = await API.surveys.parseGoal(this.goalText);
            this.aiParsed = parsed;

            let deep;
            if (this.targetAudiences.length > 1) {
                // ── Audience-Targeted Generation ──
                const audienceResult = await API.surveys.generateAudienceTargeted(
                    this.goalText,
                    this.targetAudiences,
                    parsed.research_type || 'discovery',
                    parsed.suggested_question_count || 6
                );
                this.audienceResult = audienceResult;
                this.audienceSets = audienceResult.audience_sets || [];
                this.genericSet = audienceResult.generic_set || null;

                // Flatten all questions (generic set is the "active" one for the survey DB)
                const genericQs = this.genericSet?.questions || [];
                const allAudienceQs = this.audienceSets.flatMap(s => s.questions || []);
                this.questions = genericQs;
                this.allAudienceQuestions = allAudienceQs;

                // Build a deep-compatible result for downstream steps
                deep = {
                    analysis: audienceResult.analysis || {},
                    questions: genericQs,
                    respondent_briefing: audienceResult.respondent_briefing || '',
                    interview_flow_summary: audienceResult.interview_flow_summary || ''
                };
            } else {
                // ── Standard Deep Generation ──
                deep = await API.surveys.generateDeepQuestions(
                    this.goalText,
                    parsed.research_type || 'discovery',
                    parsed.suggested_question_count || 8
                );
                this.audienceResult = null;
                this.audienceSets = [];
                this.genericSet = null;
            }

            this.deepResult = deep;
            if (!this.audienceResult) {
                this.questions = deep.questions || [];
            }

            clearInterval(loadingInterval);
            if (loadingEl) loadingEl.hidden = true;

            // Generate consent form if user opted in
            if (this.includeConsent && !this.consentFormText) {
                if (loadingTextEl) loadingTextEl.textContent = 'Generating consent form...';
                try {
                    const consentResp = await API.surveys.generateConsent(this.surveyTitle, this.goalText);
                    this.consentFormText = consentResp.consent_form || '';
                } catch (e) {
                    console.warn('Consent form generation failed:', e.message);
                }
            }

            // Create goal + survey in DB — use the user-provided title
            const surveyTitle = this.surveyTitle || parsed.title || this.goalText.substring(0, 60);
            const goal = await API.surveys.createGoal({
                title: surveyTitle,
                description: this.goalText,
                research_type: parsed.research_type || 'discovery'
            });
            const survey = await API.surveys.create({
                title: surveyTitle,
                description: this.goalText,
                research_goal_id: goal.id,
                channel_type: 'multi',
                estimated_duration: this.interviewDuration,
                interview_style: this.interviewStyle
            });
            this.survey = survey;

            // Save questions to DB (generic/main set)
            for (let i = 0; i < this.questions.length; i++) {
                const q = this.questions[i];
                try {
                    const created = await API.surveys.createQuestion({
                        survey_id: survey.id,
                        question_text: q.question_text,
                        question_type: q.question_type || 'open_ended',
                        order_index: i,
                        is_required: true,
                        follow_up_seeds: JSON.stringify(q.follow_ups || []),
                        tone: q.tone || 'neutral',
                        depth_level: q.depth || 1,
                        audience_tag: 'general'
                    });
                    this.questions[i].id = created.id;
                } catch (e) { console.error('Failed to save question:', e); }
            }

            // Save audience-specific questions to DB
            for (const aSet of this.audienceSets) {
                const audQuestions = aSet.questions || [];
                for (let i = 0; i < audQuestions.length; i++) {
                    const q = audQuestions[i];
                    try {
                        await API.surveys.createQuestion({
                            survey_id: survey.id,
                            question_text: q.question_text,
                            question_type: q.question_type || 'open_ended',
                            order_index: i,
                            is_required: true,
                            follow_up_seeds: JSON.stringify(q.follow_ups || []),
                            tone: q.tone || 'neutral',
                            depth_level: q.depth || 1,
                            audience_tag: aSet.audience
                        });
                    } catch (e) { console.error('Failed to save audience question:', e); }
                }
            }

            // Build success message
            const totalAudienceQs = this.audienceSets.reduce((sum, s) => sum + (s.questions?.length || 0), 0);
            let successMsg;
            if (this.audienceSets.length > 0) {
                successMsg = `
                    <p>✅ <strong>Analysis complete!</strong> I've generated:</p>
                    <ul style="margin:8px 0;padding-left:20px">
                        ${this.audienceSets.map(s => `<li><strong>${Helpers.escapeHtml(s.audience)}</strong>: ${s.questions?.length || 0} tailored questions</li>`).join('')}
                        <li><strong>Generic Survey</strong>: ${this.questions.length} universal questions</li>
                    </ul>
                    <p>Total: <strong>${totalAudienceQs + this.questions.length}</strong> questions with follow-ups across ${this.audienceSets.length + 1} survey variants.</p>
                    <p class="mt-1">Click <strong>"Next"</strong> to review all question sets.</p>
                `;
            } else {
                successMsg = `
                    <p>✅ <strong>Analysis complete!</strong> I've generated <strong>${this.questions.length} targeted questions</strong> with follow-up questions, all specifically aligned to your research goals.</p>
                    <p class="mt-1">Click <strong>"Next"</strong> to review the questions I've prepared.</p>
                `;
            }

            // Show success in conversation
            if (history) {
                history.innerHTML += `
                    <div class="ai-message-row">
                        <div class="ai-avatar"><i class="fas fa-robot"></i></div>
                        <div class="ai-bubble">${successMsg}</div>
                    </div>
                `;
            }

            const totalCount = totalAudienceQs + this.questions.length;
            Helpers.toast('Success', `Generated ${totalCount} questions with follow-ups!`, 'success');
            document.getElementById('btn-next-step').hidden = false;

        } catch (e) {
            console.error(e);
            if (loadingEl) loadingEl.hidden = true;
            Helpers.toast('Error', 'Failed to process. Please try again.', 'danger');
        } finally {
            this._isProcessing = false;
            const sendBtn = document.getElementById('btn-send-goal');
            if (sendBtn) { sendBtn.disabled = false; sendBtn.style.opacity = ''; }
            if (typeof loadingInterval !== 'undefined') clearInterval(loadingInterval);
        }
    },

    goStep(step) {
        if (step < 0 || step >= this.steps.length) return;
        if (step > 0 && !this.deepResult) {
            Helpers.toast('Info', 'Please describe and analyze your research goal first.', 'info');
            return;
        }
        this.currentStep = step;

        document.querySelectorAll('.wizard-step').forEach((el, i) => {
            el.classList.toggle('active', i === step);
            el.classList.toggle('completed', i < step);
        });
        document.querySelectorAll('.wizard-panel').forEach((el, i) => {
            el.classList.toggle('active', i === step);
        });

        document.getElementById('btn-prev-step').hidden = step === 0;
        const nextBtn = document.getElementById('btn-next-step');
        if (step >= this.steps.length - 1) {
            nextBtn.hidden = true;
        } else {
            nextBtn.hidden = false;
            nextBtn.innerHTML = 'Next <i class="fas fa-arrow-right"></i>';
        }

        // Render step-specific content
        if (step === 1) this.renderReview();
        if (step === 2) this.renderBriefing();
        if (step === 3) this.renderLaunch();
    },

    renderReview() {
        // Render analysis card
        const analysis = this.deepResult?.analysis || {};
        const analysisBody = document.getElementById('ai-analysis-body');
        if (analysisBody) {
            const audienceRationale = analysis.audience_rationale || '';
            analysisBody.innerHTML = `
                <div class="grid grid-2 gap-2">
                    <div class="grid-span-2">
                        <strong><i class="fas fa-bullseye"></i> Goal Summary:</strong>
                        <p class="mt-1">${Helpers.escapeHtml(analysis.goal_summary || this.goalText)}</p>
                    </div>
                    <div>
                        <strong><i class="fas fa-search"></i> Key Research Areas:</strong>
                        <div class="flex gap-1 flex-wrap mt-1">
                            ${(analysis.key_areas || []).map(a => `<span class="badge badge-primary">${Helpers.escapeHtml(a)}</span>`).join('')}
                        </div>
                    </div>
                    <div>
                        <strong><i class="fas fa-users"></i> Target Audiences:</strong>
                        ${this.audienceSets.length > 0 ? `
                            <div class="flex gap-1 flex-wrap mt-1">
                                ${this.audienceSets.map(s => `<span class="badge" style="background:#e0e7ff;color:#4338ca">${Helpers.escapeHtml(s.audience)}</span>`).join('')}
                                <span class="badge" style="background:#dcfce7;color:#16a34a">Generic</span>
                            </div>
                        ` : `<p class="mt-1 text-muted">${Helpers.escapeHtml(analysis.respondent_guidance || 'Active users')}</p>`}
                    </div>
                    <div>
                        <strong><i class="fas fa-clock"></i> Estimated Duration:</strong>
                        <p class="mt-1 text-muted">${analysis.estimated_duration || 7} minutes</p>
                    </div>
                    <div>
                        <strong><i class="fas fa-sliders"></i> Interview Style:</strong>
                        <p class="mt-1 text-muted" style="text-transform:capitalize">${Helpers.escapeHtml(this.interviewStyle || 'balanced')}</p>
                    </div>
                    <div>
                        <strong><i class="fas fa-chess"></i> Interview Approach:</strong>
                        <p class="mt-1 text-muted">${Helpers.escapeHtml(analysis.interview_approach || 'Structured interview with follow-ups')}</p>
                    </div>
                    ${audienceRationale ? `
                    <div class="grid-span-2">
                        <strong><i class="fas fa-layer-group"></i> Audience Strategy:</strong>
                        <p class="mt-1 text-muted">${Helpers.escapeHtml(audienceRationale)}</p>
                    </div>` : ''}
                </div>
            `;
        }

        // Render questions with follow-ups
        const list = document.getElementById('deep-question-list');
        if (!list) return;

        // If we have audience sets, show a tabbed UI
        if (this.audienceSets.length > 0) {
            const tabColors = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6'];
            list.innerHTML = `
                <div class="audience-tabs" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:var(--space-3);border-bottom:2px solid var(--neutral-200);padding-bottom:var(--space-2)">
                    <button class="audience-tab ${this.activeAudienceTab === 'generic' ? 'active' : ''}" data-tab="generic"
                        style="padding:8px 16px;border:2px solid ${this.activeAudienceTab === 'generic' ? '#22c55e' : 'var(--neutral-200)'};border-radius:var(--radius-md);background:${this.activeAudienceTab === 'generic' ? '#dcfce7' : 'white'};cursor:pointer;font-weight:600;font-size:0.9rem;transition:all 0.2s;font-family:inherit">
                        <i class="fas fa-globe" style="color:#22c55e"></i> Generic / All Audiences
                        <span style="font-size:0.75rem;opacity:0.7;margin-left:4px">(${this.genericSet?.questions?.length || 0})</span>
                    </button>
                    ${this.audienceSets.map((s, idx) => {
                        const color = tabColors[idx % tabColors.length];
                        const isActive = this.activeAudienceTab === s.audience;
                        return `<button class="audience-tab ${isActive ? 'active' : ''}" data-tab="${Helpers.escapeHtml(s.audience)}"
                            style="padding:8px 16px;border:2px solid ${isActive ? color : 'var(--neutral-200)'};border-radius:var(--radius-md);background:${isActive ? color + '15' : 'white'};cursor:pointer;font-weight:600;font-size:0.9rem;transition:all 0.2s;font-family:inherit">
                            <i class="fas fa-users" style="color:${color}"></i> ${Helpers.escapeHtml(s.audience)}
                            <span style="font-size:0.75rem;opacity:0.7;margin-left:4px">(${s.questions?.length || 0})</span>
                        </button>`;
                    }).join('')}
                </div>
                <div id="audience-tab-description" style="margin-bottom:var(--space-2);padding:var(--space-2) var(--space-3);background:var(--neutral-50);border-radius:var(--radius-md);font-size:0.9rem;color:var(--neutral-500)"></div>
                <div id="audience-tab-questions"></div>
            `;

            // Bind tab clicks
            list.querySelectorAll('.audience-tab').forEach(tab => {
                tab.addEventListener('click', () => {
                    this.activeAudienceTab = tab.dataset.tab;
                    this.renderReview(); // Re-render with new active tab
                });
            });

            // Render the active tab's questions
            let activeQuestions = [];
            let tabDescription = '';
            if (this.activeAudienceTab === 'generic') {
                activeQuestions = this.genericSet?.questions || [];
                tabDescription = this.genericSet?.description || 'Universal questions suitable for all respondents regardless of segment.';
            } else {
                const set = this.audienceSets.find(s => s.audience === this.activeAudienceTab);
                activeQuestions = set?.questions || [];
                tabDescription = set?.description || `Questions tailored specifically for ${this.activeAudienceTab}.`;
            }

            const descEl = document.getElementById('audience-tab-description');
            if (descEl) descEl.innerHTML = `<i class="fas fa-info-circle" style="color:var(--primary-500)"></i> ${Helpers.escapeHtml(tabDescription)}`;

            const qArea = document.getElementById('audience-tab-questions');
            if (qArea) qArea.innerHTML = this._renderQuestionCards(activeQuestions);
        } else {
            // Standard single-set view
            list.innerHTML = this._renderQuestionCards(this.questions);
        }

        this.updateQualityScore();
    },

    /** Render question cards HTML for an array of questions */
    _renderQuestionCards(questions) {
        let cards = (questions || []).map((q, i) => {
            const followUps = q.follow_ups || [];
            const depthLabel = q.depth === 1 ? 'Icebreaker' : q.depth === 2 ? 'Core' : 'Deep Dive';
            const depthColor = q.depth === 1 ? 'var(--success)' : q.depth === 2 ? 'var(--primary-500)' : 'var(--warning)';

            return `
                <div class="card mb-2" style="border-left: 4px solid ${depthColor}" id="q-card-${i}">
                    <div class="card-body" style="padding: var(--space-4)">
                        <div class="flex justify-between align-center mb-1">
                            <div class="flex align-center gap-1">
                                <span class="badge" style="background:${depthColor}; color:white">${depthLabel}</span>
                                <span class="badge">${q.question_type || 'open_ended'}</span>
                                <span class="badge" style="background: var(--neutral-100); color: var(--text-secondary)">${q.tone || 'neutral'}</span>
                            </div>
                            <div class="flex align-center gap-1">
                                <span class="text-muted" style="font-size:0.8rem">Q${i + 1}</span>
                                <button class="btn btn-sm" style="padding:4px 8px;background:none;color:var(--primary-500);border:1px solid var(--primary-500);font-size:0.75rem" onclick="SurveyDesigner.editQuestion(${i})" title="Edit">
                                    <i class="fas fa-pen"></i>
                                </button>
                                <button class="btn btn-sm" style="padding:4px 8px;background:none;color:var(--danger);border:1px solid var(--danger);font-size:0.75rem" onclick="SurveyDesigner.deleteQuestion(${i})" title="Delete">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <h3 style="font-size: 1rem; font-weight: 600; margin: var(--space-2) 0">${Helpers.escapeHtml(q.question_text)}</h3>
                        ${q.purpose ? `<p class="text-muted" style="font-size:0.85rem; font-style:italic"><i class="fas fa-lightbulb" style="color:var(--warning)"></i> Purpose: ${Helpers.escapeHtml(q.purpose)}</p>` : ''}
                        
                        ${followUps.length > 0 ? `
                            <div style="margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px dashed var(--border-light)">
                                <p style="font-size:0.8rem; font-weight:600; color:var(--primary-500); margin-bottom: var(--space-2)">
                                    <i class="fas fa-code-branch"></i> Follow-up Questions:
                                </p>
                                ${followUps.map((fu, fi) => `
                                    <div style="margin-left: var(--space-4); padding: var(--space-2) var(--space-3); background: var(--bg-secondary); border-radius: var(--radius-md); margin-bottom: var(--space-2)">
                                        <p style="font-size:0.75rem; color: var(--text-tertiary); margin-bottom: 4px">
                                            <i class="fas fa-arrow-right"></i> ${Helpers.escapeHtml(fu.trigger || 'Based on response')}
                                        </p>
                                        <p style="font-size:0.9rem">${Helpers.escapeHtml(fu.question_text)}</p>
                                    </div>
                                `).join('')}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        // Add question button at the bottom
        cards += `
            <div style="text-align:center;margin-top:var(--space-3)">
                <button class="btn btn-secondary" onclick="SurveyDesigner.addQuestion()" style="gap:8px">
                    <i class="fas fa-plus"></i> Add Question
                </button>
            </div>
        `;
        return cards;
    },

    /** Edit a question inline */
    editQuestion(index) {
        const questions = this._getActiveQuestions();
        const q = questions[index];
        if (!q) return;

        const card = document.getElementById('q-card-' + index);
        if (!card) return;

        const body = card.querySelector('.card-body');
        body.innerHTML = `
            <div style="padding:var(--space-2)">
                <label style="font-weight:600;font-size:0.85rem;margin-bottom:6px;display:block">Question Text</label>
                <textarea id="edit-q-text-${index}" rows="3" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:var(--radius-md);font-size:0.95rem;resize:vertical">${Helpers.escapeHtml(q.question_text)}</textarea>
                <div class="flex gap-2 mt-2">
                    <button class="btn btn-primary btn-sm" onclick="SurveyDesigner.saveQuestionEdit(${index})">
                        <i class="fas fa-check"></i> Save
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="SurveyDesigner.renderReview()">
                        <i class="fas fa-times"></i> Cancel
                    </button>
                </div>
            </div>
        `;
        document.getElementById('edit-q-text-' + index)?.focus();
    },

    /** Save an edited question */
    async saveQuestionEdit(index) {
        const textarea = document.getElementById('edit-q-text-' + index);
        if (!textarea) return;
        const newText = textarea.value.trim();
        if (!newText) { Helpers.toast('Error', 'Question text cannot be empty.', 'warning'); return; }

        const questions = this._getActiveQuestions();
        questions[index].question_text = newText;

        // Update in DB if the question has an id, otherwise create it
        if (questions[index].id) {
            try {
                await API.surveys.updateQuestion(questions[index].id, { question_text: newText });
            } catch (e) { console.warn('Failed to update question in DB:', e); }
        } else if (this.survey?.id) {
            try {
                const audienceTag = this.audienceSets.length > 0
                    ? (this.activeAudienceTab === 'generic' ? 'general' : this.activeAudienceTab)
                    : 'general';
                const created = await API.surveys.createQuestion({
                    survey_id: this.survey.id,
                    question_text: newText,
                    question_type: questions[index].question_type || 'open_ended',
                    order_index: index,
                    is_required: true,
                    follow_up_seeds: JSON.stringify(questions[index].follow_ups || []),
                    tone: questions[index].tone || 'neutral',
                    depth_level: questions[index].depth || 2,
                    audience_tag: audienceTag
                });
                questions[index].id = created?.id;
            } catch (e) {
                console.warn('Failed to create new question in DB:', e);
            }
        }

        Helpers.toast('Updated', 'Question text saved.', 'success', 2000);
        this.renderReview();
    },

    /** Delete a question */
    async deleteQuestion(index) {
        const questions = this._getActiveQuestions();
        if (questions.length <= 1) {
            Helpers.toast('Cannot Delete', 'You need at least one question.', 'warning');
            return;
        }
        const q = questions[index];
        if (!confirm('Delete this question?\n\n"' + q.question_text.substring(0, 80) + '..."')) return;

        // Remove from DB if saved
        if (q.id) {
            try { await API.surveys.deleteQuestion(q.id); } catch (e) { console.warn('DB delete failed:', e); }
        }

        questions.splice(index, 1);
        Helpers.toast('Deleted', 'Question removed.', 'success', 2000);
        this.renderReview();
    },

    /** Add a new question manually */
    async addQuestion() {
        const questions = this._getActiveQuestions();
        const newQ = {
            question_text: '',
            question_type: 'open_ended',
            tone: 'neutral',
            depth: 2,
            follow_ups: [],
            purpose: ''
        };

        // Add placeholder and render edit inline
        questions.push(newQ);
        this.renderReview();

        // Immediately open edit for the new question
        setTimeout(() => this.editQuestion(questions.length - 1), 100);
    },

    /** Get the currently active question set (generic or audience-specific) */
    _getActiveQuestions() {
        if (this.audienceSets.length > 0) {
            if (this.activeAudienceTab === 'generic') {
                return this.genericSet?.questions || this.questions;
            }
            const set = this.audienceSets.find(s => s.audience === this.activeAudienceTab);
            return set?.questions || [];
        }
        return this.questions;
    },

    renderBriefing() {
        const briefingContent = document.getElementById('briefing-content');
        const flowSummary = document.getElementById('flow-summary');
        const questionsPreview = document.getElementById('briefing-questions-preview');

        if (briefingContent) {
            const briefing = this.deepResult?.respondent_briefing || 'The interview will cover your experience, preferences, and suggestions.';
            briefingContent.innerHTML = `
                <div style="background: var(--bg-secondary); padding: var(--space-4); border-radius: var(--radius-lg); font-size: 1.05rem; line-height: 1.7">
                    <i class="fas fa-quote-left" style="color:var(--primary-500); font-size:1.2rem"></i>
                    <p style="margin: var(--space-2) 0">${Helpers.escapeHtml(briefing)}</p>
                    <i class="fas fa-quote-right" style="color:var(--primary-500); font-size:1.2rem; float:right"></i>
                </div>
                <div class="mt-3">
                    <div class="flex gap-3 flex-wrap">
                        <div class="flex align-center gap-1">
                            <i class="fas fa-list-ol" style="color:var(--primary-500)"></i>
                            <strong>${this.questions.length}</strong> main questions
                        </div>
                        <div class="flex align-center gap-1">
                            <i class="fas fa-code-branch" style="color:var(--warning)"></i>
                            <strong>${this.questions.reduce((sum, q) => sum + (q.follow_ups?.length || 0), 0)}</strong> follow-up questions
                        </div>
                        <div class="flex align-center gap-1">
                            <i class="fas fa-clock" style="color:var(--success)"></i>
                            ~<strong>${this.deepResult?.analysis?.estimated_duration || 7}</strong> minutes
                        </div>
                    </div>
                </div>
                <div class="mt-3" style="background: #f0f4ff; padding: var(--space-3); border-radius: var(--radius-md);">
                    <p style="font-size:0.9rem; color: #3b5998">
                        <i class="fas fa-robot"></i> <strong>Note:</strong> The AI interviewer will adapt in real-time. If a respondent gives a brief or interesting answer, the AI will automatically ask relevant follow-up questions to dig deeper.
                    </p>
                </div>
            `;
        }

        if (flowSummary) {
            const flowText = this.deepResult?.interview_flow_summary || '';
            const icebreakers = this.questions.filter(q => q.depth === 1);
            const core = this.questions.filter(q => q.depth === 2);
            const deep = this.questions.filter(q => q.depth === 3);

            flowSummary.innerHTML = `
                ${flowText ? `<p class="mb-3 text-muted">${Helpers.escapeHtml(flowText)}</p>` : ''}
                <div style="display:flex; flex-direction:column; gap: var(--space-2)">
                    <div style="display:flex; align-items:center; gap: var(--space-3)">
                        <div style="width:40px; height:40px; border-radius:50%; background:var(--success); color:white; display:flex; align-items:center; justify-content:center; flex-shrink:0">
                            <i class="fas fa-hand-wave"></i>
                        </div>
                        <div>
                            <strong>Warm-up Phase</strong> — ${icebreakers.length || 1} icebreaker question${icebreakers.length !== 1 ? 's' : ''}
                            <p class="text-muted" style="font-size:0.85rem">Build rapport and make the respondent comfortable</p>
                        </div>
                    </div>
                    <div style="width:2px; height:20px; background:var(--border-light); margin-left:19px"></div>
                    <div style="display:flex; align-items:center; gap: var(--space-3)">
                        <div style="width:40px; height:40px; border-radius:50%; background:var(--primary-500); color:white; display:flex; align-items:center; justify-content:center; flex-shrink:0">
                            <i class="fas fa-search"></i>
                        </div>
                        <div>
                            <strong>Core Exploration</strong> — ${core.length || Math.max(1, this.questions.length - 2)} main questions + follow-ups
                            <p class="text-muted" style="font-size:0.85rem">Deep dive into key research areas with adaptive follow-ups</p>
                        </div>
                    </div>
                    <div style="width:2px; height:20px; background:var(--border-light); margin-left:19px"></div>
                    <div style="display:flex; align-items:center; gap: var(--space-3)">
                        <div style="width:40px; height:40px; border-radius:50%; background:var(--warning); color:white; display:flex; align-items:center; justify-content:center; flex-shrink:0">
                            <i class="fas fa-lightbulb"></i>
                        </div>
                        <div>
                            <strong>Reflective Close</strong> — ${deep.length || 1} closing question${deep.length !== 1 ? 's' : ''}
                            <p class="text-muted" style="font-size:0.85rem">Gather final thoughts and forward-looking suggestions</p>
                        </div>
                    </div>
                </div>
            `;
        }

        if (questionsPreview) {
            questionsPreview.innerHTML = this.questions.map((q, i) => `
                <div style="padding: var(--space-2) 0; ${i < this.questions.length - 1 ? 'border-bottom: 1px solid var(--border-light);' : ''}">
                    <div style="display:flex; align-items:center; gap: var(--space-2)">
                        <span style="width:28px; height:28px; border-radius:50%; background:#e8edff; color:var(--primary-500); display:flex; align-items:center; justify-content:center; font-weight:600; font-size:0.8rem; flex-shrink:0">${i + 1}</span>
                        <span>${Helpers.escapeHtml(q.question_text)}</span>
                    </div>
                    ${(q.follow_ups || []).length > 0 ? `
                        <div class="text-muted" style="font-size:0.8rem; margin-left: 44px; margin-top: 4px">
                            + ${q.follow_ups.length} follow-up question${q.follow_ups.length > 1 ? 's' : ''} based on response
                        </div>
                    ` : ''}
                </div>
            `).join('');
        }
    },

    renderLaunch() {
        // Re-bind channel cards
        document.querySelectorAll('.channel-launch-card').forEach(card => {
            card.addEventListener('click', () => this.launchSurvey(card.dataset.channel));
            card.addEventListener('mouseenter', () => card.style.transform = 'translateY(-4px)');
            card.addEventListener('mouseleave', () => card.style.transform = 'translateY(0)');
        });
    },

    async launchSurvey(channel) {
        if (!this.survey) {
            Helpers.toast('Error', 'No survey created yet. Please go back and complete the design.', 'error');
            return;
        }

        const statusEl = document.getElementById('launch-status');
        const statusText = document.getElementById('launch-status-text');

        // Disable channel cards and show loading
        document.querySelectorAll('.channel-launch-card').forEach(c => {
            c.style.pointerEvents = 'none';
            c.style.opacity = '0.6';
        });
        if (statusEl) {
            statusEl.hidden = false;
            statusEl.innerHTML = `<div style="text-align:center;padding:var(--space-3)"><div class="spinner" style="margin:0 auto var(--space-2)"></div><p class="text-muted">Publishing your survey...</p></div>`;
        }

        try {
            // Publish the survey with all channels enabled
            const result = await API.publish.publish({
                survey_id: this.survey.id,
                title: this.surveyTitle || this.survey.title || this.aiParsed?.title || 'Untitled Survey',
                description: this.goalText,
                web_form_enabled: true,
                chat_enabled: true,
                audio_enabled: true,
                require_email: true,
                consent_form_text: this.includeConsent ? this.consentFormText : ''
            });

            const baseUrl = window.location.origin;
            const links = result.links || {};
            const shareCode = result.share_code;

            if (statusEl) statusEl.hidden = false;
            if (statusEl) statusEl.innerHTML = `
                <div class="card" style="border-left: 4px solid var(--success); text-align:left; padding: var(--space-4)">
                    <p style="margin-bottom:var(--space-3)"><i class="fas fa-check-circle" style="color:var(--success)"></i> <strong>Survey published successfully!</strong></p>
                    <p class="text-muted" style="margin-bottom:var(--space-3)">Share these links with your respondents:</p>

                    <div style="margin-bottom:12px;padding:12px;background:var(--neutral-50);border-radius:var(--radius-md)">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                            <i class="fas fa-link" style="color:var(--primary-500)"></i>
                            <strong>Landing Page</strong> <span class="text-muted" style="font-size:0.8rem">(respondent chooses method)</span>
                        </div>
                        <div style="display:flex;gap:6px">
                            <input type="text" value="${baseUrl}${links.landing || '/interview/' + shareCode}" readonly style="flex:1;padding:8px;border:1px solid var(--border);border-radius:var(--radius-md);font-size:0.85rem" onclick="this.select()">
                            <button class="btn btn-primary btn-sm" onclick="navigator.clipboard.writeText('${baseUrl}${links.landing || '/interview/' + shareCode}');this.innerHTML='<i class=\\'fas fa-check\\'></i> Copied'"><i class="fas fa-copy"></i> Copy</button>
                        </div>
                    </div>

                    <div style="margin-bottom:12px;padding:12px;background:var(--neutral-50);border-radius:var(--radius-md)">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                            <i class="fas fa-clipboard-list" style="color:var(--primary-500)"></i>
                            <strong>Web Form</strong>
                        </div>
                        <div style="display:flex;gap:6px">
                            <input type="text" value="${baseUrl}${links.web_form || '/interview/' + shareCode + '/web-form'}" readonly style="flex:1;padding:8px;border:1px solid var(--border);border-radius:var(--radius-md);font-size:0.85rem" onclick="this.select()">
                            <button class="btn btn-primary btn-sm" onclick="navigator.clipboard.writeText('${baseUrl}${links.web_form || '/interview/' + shareCode + '/web-form'}');this.innerHTML='<i class=\\'fas fa-check\\'></i> Copied'"><i class="fas fa-copy"></i> Copy</button>
                        </div>
                    </div>

                    <div style="margin-bottom:12px;padding:12px;background:var(--neutral-50);border-radius:var(--radius-md)">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                            <i class="fas fa-comments" style="color:#8b5cf6"></i>
                            <strong>Chat Interview</strong>
                        </div>
                        <div style="display:flex;gap:6px">
                            <input type="text" value="${baseUrl}${links.chat || '/interview/' + shareCode + '/chat'}" readonly style="flex:1;padding:8px;border:1px solid var(--border);border-radius:var(--radius-md);font-size:0.85rem" onclick="this.select()">
                            <button class="btn btn-primary btn-sm" onclick="navigator.clipboard.writeText('${baseUrl}${links.chat || '/interview/' + shareCode + '/chat'}');this.innerHTML='<i class=\\'fas fa-check\\'></i> Copied'"><i class="fas fa-copy"></i> Copy</button>
                        </div>
                    </div>

                    <div style="padding:12px;background:var(--neutral-50);border-radius:var(--radius-md)">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                            <i class="fas fa-microphone" style="color:var(--warning)"></i>
                            <strong>Audio Interview</strong>
                        </div>
                        <div style="display:flex;gap:6px">
                            <input type="text" value="${baseUrl}${links.audio || '/interview/' + shareCode + '/audio'}" readonly style="flex:1;padding:8px;border:1px solid var(--border);border-radius:var(--radius-md);font-size:0.85rem" onclick="this.select()">
                            <button class="btn btn-primary btn-sm" onclick="navigator.clipboard.writeText('${baseUrl}${links.audio || '/interview/' + shareCode + '/audio'}');this.innerHTML='<i class=\\'fas fa-check\\'></i> Copied'"><i class="fas fa-copy"></i> Copy</button>
                        </div>
                    </div>

                    <div style="margin-top:16px;display:flex;gap:8px">
                        <button class="btn btn-primary" onclick="window.location.hash='my-surveys'"><i class="fas fa-folder-open"></i> View in My Surveys</button>
                        <button class="btn btn-secondary" onclick="window.open('${baseUrl}${links.landing || '/interview/' + shareCode}', '_blank')"><i class="fas fa-external-link-alt"></i> Preview</button>
                    </div>
                </div>`;

            Helpers.toast('Published!', 'Survey is now live. Share the links with your respondents!', 'success');

        } catch (e) {
            // If already published, show the existing links
            if (e.message && e.message.includes('already published')) {
                Helpers.toast('Info', 'This survey was already published. Check My Surveys for links.', 'info');
                setTimeout(() => { window.location.hash = 'my-surveys'; }, 1500);
            } else {
                Helpers.toast('Error', e.message || 'Failed to publish', 'error');
            }
            // Re-enable channel cards
            document.querySelectorAll('.channel-launch-card').forEach(c => {
                c.style.pointerEvents = 'auto';
                c.style.opacity = '1';
            });
        }
    },

    updateQualityScore() {
        const container = document.getElementById('quality-score-container');
        if (!container || this.questions.length === 0) return;

        let score = 0;
        const total = this.questions.length;

        if (total >= 5 && total <= 12) score += 25;
        else if (total >= 3) score += 15;

        const hasOpen = this.questions.some(q => (q.question_type || 'open_ended') === 'open_ended');
        const hasRating = this.questions.some(q => q.question_type === 'rating' || q.question_type === 'scale');
        if (hasOpen && hasRating) score += 20;
        else if (hasOpen) score += 10;

        const hasFollowUps = this.questions.some(q => (q.follow_ups || []).length > 0);
        if (hasFollowUps) score += 25;

        const hasDepthVariety = new Set(this.questions.map(q => q.depth || 1)).size >= 2;
        if (hasDepthVariety) score += 15;

        const hasPurpose = this.questions.some(q => q.purpose);
        if (hasPurpose) score += 15;

        score = Math.min(100, score);

        const circle = document.getElementById('quality-ring-circle');
        const label = document.getElementById('quality-ring-value');
        if (circle && label) {
            const offset = 283 - (283 * score / 100);
            circle.style.strokeDashoffset = offset;
            circle.style.stroke = score >= 75 ? 'var(--success)' : score >= 50 ? 'var(--warning)' : 'var(--danger)';
            label.textContent = score;
        }
    },

    destroy() {}
};
