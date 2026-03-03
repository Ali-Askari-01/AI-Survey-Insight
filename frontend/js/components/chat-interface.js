/**
 * Chat Interface Component — WhatsApp-style conversational interview
 * Feature 2: Multi-Channel Collection (Chat channel)
 */
const ChatInterface = {
    session: null,
    messages: [],
    surveyId: null,        // Dynamically loaded — no hardcoding
    totalQuestions: 5,
    isTyping: false,

    async init() {
        this.render();
        this.bindEvents();
        await this.loadActiveSurvey();
        await this.startChat();
    },

    async loadActiveSurvey() {
        /**
         * Dynamically find the user's most recent survey.
         * Falls back to survey id 1 only if no surveys exist.
         */
        try {
            const surveys = await API.surveys.list();
            if (surveys && surveys.length > 0) {
                // Use the most recently created survey
                this.surveyId = surveys[0].id;
            } else {
                this.surveyId = 1;
            }
        } catch (e) {
            console.warn('Could not load surveys, defaulting to id=1:', e);
            this.surveyId = 1;
        }
    },

    render() {
        const page = document.getElementById('page-chat');
        if (!page) return;
        page.innerHTML = `
            <div class="chat-container">
                <div class="chat-header">
                    <div class="chat-header-left">
                        <div class="chat-avatar"><i class="fas fa-robot"></i></div>
                        <div>
                            <div class="chat-name">AI Interviewer</div>
                            <div class="chat-status" id="chat-status">Online</div>
                        </div>
                    </div>
                    <div class="chat-header-right">
                        <div class="chat-progress-bar">
                            <div class="chat-progress" id="chat-progress" style="width:0%"></div>
                        </div>
                    </div>
                </div>
                <div class="chat-messages" id="chat-messages">
                    <!-- Messages rendered here -->
                </div>
                <div id="quick-replies-container" class="quick-replies" hidden></div>
                <div class="chat-input-area">
                    <div class="chat-input-wrapper">
                        <button class="btn btn-icon btn-ghost chat-emoji-btn" id="emoji-btn" title="Emoji">
                            <i class="fas fa-smile"></i>
                        </button>
                        <textarea id="chat-input" placeholder="Type a message..." rows="1"></textarea>
                        <button class="btn btn-icon btn-ghost chat-attach-btn" title="Attach file">
                            <i class="fas fa-paperclip"></i>
                        </button>
                        <button class="btn btn-icon btn-primary chat-send-btn" id="chat-send" title="Send">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    },

    bindEvents() {
        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('chat-send');

        sendBtn?.addEventListener('click', () => this.sendMessage());

        input?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        input?.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 100) + 'px';
        });

        // Emoji button (simple)
        document.getElementById('emoji-btn')?.addEventListener('click', () => {
            const emojis = ['👍', '👎', '😊', '😞', '🤔', '❤️', '🔥', '💡'];
            const picker = document.createElement('div');
            picker.className = 'emoji-picker';
            picker.style.cssText = 'position:absolute;bottom:60px;left:12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:8px;display:flex;gap:4px;z-index:10;box-shadow:var(--shadow-lg)';
            picker.innerHTML = emojis.map(e => `<button class="btn btn-ghost" style="font-size:1.4rem;padding:4px">${e}</button>`).join('');
            picker.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', () => {
                    input.value += btn.textContent;
                    input.focus();
                    picker.remove();
                });
            });
            document.querySelector('.chat-input-area')?.appendChild(picker);
            setTimeout(() => {
                document.addEventListener('click', function handler(e) {
                    if (!picker.contains(e.target)) { picker.remove(); document.removeEventListener('click', handler); }
                });
            }, 10);
        });
    },

    async startChat() {
        try {
            // Create chat session using the dynamically loaded survey
            this.session = await API.interviews.createSession({
                survey_id: this.surveyId,
                channel: 'chat',
                respondent_id: 'chat_user_' + Helpers.uid()
            });

            this.totalQuestions = this.session.total_questions || 5;

            // Load any existing history
            try {
                const history = await API.interviews.getHistory(this.session.session_id);
                if (history.length > 0) {
                    this.messages = history;
                    this.renderMessages();
                }
            } catch (e) { /* new session */ }

            // Use the dynamic intro message from the API (which is survey-context aware)
            const introMessage = this.session.intro_message || "Hi there! 👋 I'm your AI research interviewer. I'll be asking you a few questions. Ready to start?";
            this.addAIMessage(introMessage, [
                "I'm ready to start!",
                "What will you ask about?",
                "How long will this take?"
            ]);

            // Update header with survey title if available
            const chatName = document.querySelector('.chat-name');
            if (chatName && this.session.survey_title) {
                chatName.textContent = `AI Interviewer — ${this.session.survey_title}`;
            }

        } catch (e) {
            console.error('Failed to start chat:', e);
            const container = document.getElementById('chat-messages');
            if (container) {
                container.innerHTML = `
                    <div class="chat-message ai-message">
                        <div class="message-avatar"><i class="fas fa-robot"></i></div>
                        <div class="message-content">
                            <div class="message-bubble">
                                <p>Sorry, I couldn't start the interview session.</p>
                                <p style="font-size:0.85rem;color:var(--neutral-500);margin-top:8px">${e.message || 'Connection error'}</p>
                                <button class="btn btn-primary btn-sm" style="margin-top:12px" onclick="ChatInterface.startChat()">
                                    <i class="fas fa-redo"></i> Retry
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }
        }
    },

    async sendMessage(text) {
        const input = document.getElementById('chat-input');
        const messageText = text || input?.value.trim();
        if (!messageText) return;

        if (input) {
            input.value = '';
            input.style.height = 'auto';
        }

        // Hide quick replies
        document.getElementById('quick-replies-container').hidden = true;

        // Add user message
        this.addUserMessage(messageText);

        // Show typing indicator and disable send
        this.showTyping();
        const sendBtn = document.getElementById('chat-send');
        if (sendBtn) sendBtn.disabled = true;

        try {
            // Send to API
            const response = await API.interviews.chat({
                session_id: this.session.session_id,
                message: messageText,
                message_type: 'text'
            });

            // Hide typing after delay (simulate thinking)
            await this.delay(800 + Math.random() * 1200);
            this.hideTyping();
            if (sendBtn) sendBtn.disabled = false;

            // Show AI response
            const aiText = response.ai_message || response.ai_response || response.message || "Thank you for your response. Let me think about a follow-up question...";
            const quickReplies = response.quick_replies || [];

            this.addAIMessage(aiText, quickReplies);

            // Update progress from server-calculated value
            if (response.progress !== undefined) {
                document.getElementById('chat-progress').style.width = response.progress + '%';
            }

            if (response.interview_complete) {
                this.showCompletion();
            }

        } catch (e) {
            this.hideTyping();
            if (sendBtn) sendBtn.disabled = false;
            this._lastFailedMessage = messageText;
            const container = document.getElementById('chat-messages');
            if (container) {
                const retryDiv = document.createElement('div');
                retryDiv.className = 'chat-message ai-message';
                retryDiv.innerHTML = `
                    <div class="message-avatar"><i class="fas fa-robot"></i></div>
                    <div class="message-content">
                        <div class="message-bubble" style="border-left:3px solid var(--danger)">
                            <p>I had trouble processing that. This might be a temporary issue.</p>
                            <div style="display:flex;gap:8px;margin-top:10px">
                                <button class="btn btn-primary btn-sm" onclick="ChatInterface.retrySend()">
                                    <i class="fas fa-redo"></i> Retry
                                </button>
                                <button class="btn btn-secondary btn-sm" onclick="document.getElementById('chat-input').focus();this.closest('.chat-message').remove()">
                                    <i class="fas fa-edit"></i> Edit & Resend
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                container.appendChild(retryDiv);
                container.scrollTop = container.scrollHeight;
            }
        }
    },

    async retrySend() {
        if (this._lastFailedMessage) {
            // Remove the retry prompt
            const msgs = document.querySelectorAll('.chat-message.ai-message');
            const last = msgs[msgs.length - 1];
            if (last?.querySelector('.fa-redo')) last.remove();
            await this.sendMessage(this._lastFailedMessage);
        }
    },

    addUserMessage(text) {
        const msg = { sender: 'user', message: text, timestamp: new Date().toISOString() };
        this.messages.push(msg);
        this.appendMessage(msg);
    },

    addAIMessage(text, quickReplies = []) {
        const msg = { sender: 'ai', message: text, timestamp: new Date().toISOString() };
        this.messages.push(msg);
        this.appendMessage(msg);

        if (quickReplies.length > 0) {
            this.showQuickReplies(quickReplies);
        }
    },

    appendMessage(msg) {
        const container = document.getElementById('chat-messages');
        if (!container) return;

        const sender = msg.sender || msg.role || 'user';
        const text = msg.message || msg.text || '';
        const ts = msg.timestamp || msg.created_at;
        const msgId = 'msg-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);

        const div = document.createElement('div');
        div.className = `chat-message ${sender === 'ai' ? 'ai-message' : 'user-message'}`;

        const emojiReactions = `
            <div class="message-reactions" id="reactions-${msgId}">
                <button class="reaction-btn" data-emoji="👍" title="Thumbs up">👍</button>
                <button class="reaction-btn" data-emoji="👎" title="Thumbs down">👎</button>
                <button class="reaction-btn" data-emoji="💡" title="Insightful">💡</button>
                <button class="reaction-btn" data-emoji="❤️" title="Love it">❤️</button>
            </div>
        `;

        if (sender === 'ai') {
            div.innerHTML = `
                <div class="message-avatar"><i class="fas fa-robot"></i></div>
                <div class="message-content">
                    <div class="message-bubble">${this.formatMessage(text)}</div>
                    ${emojiReactions}
                    <div class="message-time">${this.formatTime(ts)}</div>
                </div>
            `;
        } else {
            div.innerHTML = `
                <div class="message-content">
                    <div class="message-bubble">${Helpers.escapeHtml(text)}</div>
                    ${emojiReactions}
                    <div class="message-time">${this.formatTime(ts)}</div>
                </div>
            `;
        }

        // Bind emoji reaction buttons
        div.querySelectorAll('.reaction-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                btn.classList.toggle('reacted');
                if (btn.classList.contains('reacted')) {
                    btn.style.background = 'var(--primary-100, #e0e7ff)';
                    btn.style.transform = 'scale(1.2)';
                    setTimeout(() => btn.style.transform = '', 200);
                } else {
                    btn.style.background = '';
                }
            });
        });

        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    },

    renderMessages() {
        const container = document.getElementById('chat-messages');
        if (!container) return;
        container.innerHTML = '';
        this.messages.forEach(msg => this.appendMessage(msg));
    },

    showQuickReplies(replies) {
        const container = document.getElementById('quick-replies-container');
        if (!container) return;
        container.hidden = false;
        container.innerHTML = replies.map(r =>
            `<button class="quick-reply-btn">${Helpers.escapeHtml(r)}</button>`
        ).join('');

        container.querySelectorAll('.quick-reply-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.sendMessage(btn.textContent);
            });
        });
    },

    showTyping() {
        this.isTyping = true;
        const container = document.getElementById('chat-messages');
        if (!container) return;

        const status = document.getElementById('chat-status');
        if (status) status.textContent = 'Typing...';

        const indicator = document.createElement('div');
        indicator.className = 'chat-message ai-message typing-message';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content">
                <div class="message-bubble">
                    <div class="typing-indicator"><span></span><span></span><span></span></div>
                </div>
            </div>
        `;
        container.appendChild(indicator);
        container.scrollTop = container.scrollHeight;
    },

    hideTyping() {
        this.isTyping = false;
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
        const status = document.getElementById('chat-status');
        if (status) status.textContent = 'Online';
    },

    showCompletion() {
        this.addAIMessage("🎉 Thank you so much for your responses! Your feedback is incredibly valuable. The interview is now complete. Let me generate your transcript and report...");
        const input = document.getElementById('chat-input');
        if (input) input.disabled = true;
        const sendBtn = document.getElementById('chat-send');
        if (sendBtn) sendBtn.disabled = true;

        // Generate transcript & report
        this.generateTranscriptReport();
    },

    async generateTranscriptReport() {
        try {
            const result = await API.interviews.completeInterview(this.session.session_id);
            const report = result.report || {};

            // Build report HTML
            const reportHTML = this.buildReportHTML(report);

            // Show report in chat
            const container = document.getElementById('chat-messages');
            if (container) {
                const reportDiv = document.createElement('div');
                reportDiv.className = 'chat-message ai-message';
                reportDiv.innerHTML = `
                    <div class="message-avatar"><i class="fas fa-robot"></i></div>
                    <div class="message-content" style="max-width:90%">
                        <div class="message-bubble" style="background: white; border: 1px solid var(--border-light); padding: 0; overflow: hidden; border-radius: var(--radius-lg)">
                            ${reportHTML}
                        </div>
                        <div class="message-time">${this.formatTime(new Date().toISOString())}</div>
                    </div>
                `;
                container.appendChild(reportDiv);
                container.scrollTop = container.scrollHeight;
            }
        } catch (e) {
            console.error('Failed to generate report:', e);
            this.addAIMessage("I've recorded all your responses. The detailed transcript report will be available in the Reports section.");
        }
    },

    buildReportHTML(report) {
        const ts = report.transcript_summary || {};
        const analysis = report.overall_analysis || {};
        const qSummaries = report.question_summaries || [];
        const recommendations = report.recommendations || [];
        const execSummary = report.executive_summary || '';

        let html = `
            <div style="padding: var(--space-4); background: linear-gradient(135deg, var(--primary-500), var(--primary-700)); color: white;">
                <h3 style="color:white; margin-bottom: 4px"><i class="fas fa-file-alt"></i> Interview Transcript & Report</h3>
                <p style="opacity: 0.85; font-size: 0.85rem">${ts.total_questions_asked || 0} questions · ${ts.total_responses || 0} responses · ${ts.duration_estimate || 'N/A'}</p>
            </div>
        `;

        // Executive Summary
        if (execSummary) {
            html += `
                <div style="padding: var(--space-4); border-bottom: 1px solid var(--border-light)">
                    <h4 style="margin-bottom: var(--space-2)"><i class="fas fa-align-left" style="color:var(--primary-500)"></i> Executive Summary</h4>
                    <p style="line-height:1.7; color: var(--text-secondary)">${Helpers.escapeHtml(execSummary)}</p>
                </div>
            `;
        }

        // Question Summaries
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
                        ${(qs.notable_quotes || []).length > 0 ? `
                            <div style="margin-top: 6px; font-size:0.8rem; font-style:italic; color: var(--text-tertiary)">
                                ${qs.notable_quotes.map(q => `"${Helpers.escapeHtml(q)}"`).join(' · ')}
                            </div>
                        ` : ''}
                    </div>
                `;
            });
            html += `</div>`;
        }

        // Overall Analysis
        if (analysis.main_pain_points?.length || analysis.positive_highlights?.length || analysis.suggestions_made?.length) {
            html += `<div style="padding: var(--space-4); border-bottom: 1px solid var(--border-light)">`;
            html += `<h4 style="margin-bottom: var(--space-3)"><i class="fas fa-chart-pie" style="color:var(--primary-500)"></i> Analysis</h4>`;

            if (analysis.respondent_sentiment) {
                html += `<p style="margin-bottom: var(--space-2)"><strong>Overall Sentiment:</strong> ${Helpers.escapeHtml(analysis.respondent_sentiment)}</p>`;
            }
            if (analysis.emotional_journey) {
                html += `<p style="margin-bottom: var(--space-3); font-size:0.9rem; color:var(--text-secondary)"><i class="fas fa-heart"></i> ${Helpers.escapeHtml(analysis.emotional_journey)}</p>`;
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

        // Recommendations
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

        return html;
    },

    formatMessage(text) {
        // Convert **bold** and URLs
        let html = Helpers.escapeHtml(text);
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/(https?:\/\/\S+)/g, '<a href="$1" target="_blank">$1</a>');
        return html;
    },

    formatTime(ts) {
        if (!ts) return '';
        try {
            const d = new Date(ts);
            if (isNaN(d.getTime())) return '';
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch { return ''; }
    },

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    destroy() {}
};
