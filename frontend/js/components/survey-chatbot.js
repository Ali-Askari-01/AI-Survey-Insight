/**
 * Survey Analysis Chatbot Component
 * AI-powered conversational Q&A about survey data, insights, and responses.
 * Appears as a floating panel on the Insights page.
 */
const SurveyChatbot = {
    surveyId: null,
    conversationId: null,
    messages: [],
    isOpen: false,
    isLoading: false,
    persona: 'analyst',
    suggestedQuestions: [
        "What are the top themes from this survey?",
        "What is the overall sentiment of respondents?",
        "Compare positive vs negative feedback themes",
        "What are the most critical issues raised?",
        "How does user satisfaction differ across feature areas?",
        "Summarize the key findings in 3 bullet points"
    ],

    init(surveyId) {
        this.surveyId = surveyId;
        this.conversationId = null;
        this.messages = [];
        this.persona = localStorage.getItem('chatbot_persona') || 'analyst';
        this.renderToggleButton();
    },

    setSurveyId(surveyId) {
        if (this.surveyId !== surveyId) {
            this.surveyId = surveyId;
            this.conversationId = null;
            this.messages = [];
            if (this.isOpen) {
                this.renderChatPanel();
            }
        }
    },

    renderToggleButton() {
        // Remove existing button if any
        document.getElementById('chatbot-toggle-btn')?.remove();

        const btn = document.createElement('button');
        btn.id = 'chatbot-toggle-btn';
        btn.className = 'chatbot-toggle-btn';
        btn.innerHTML = '<i class="fas fa-robot"></i><span class="chatbot-toggle-label">Ask AI</span>';
        btn.title = 'Ask AI about this survey';
        btn.addEventListener('click', () => this.toggle());
        document.body.appendChild(btn);
    },

    toggle() {
        this.isOpen = !this.isOpen;
        if (this.isOpen) {
            this.renderChatPanel();
            document.getElementById('chatbot-toggle-btn')?.classList.add('active');
        } else {
            document.getElementById('chatbot-panel')?.remove();
            document.getElementById('chatbot-toggle-btn')?.classList.remove('active');
        }
    },

    open() {
        if (!this.isOpen) this.toggle();
    },

    close() {
        if (this.isOpen) this.toggle();
    },

    renderChatPanel() {
        // Remove if exists
        document.getElementById('chatbot-panel')?.remove();

        const panel = document.createElement('div');
        panel.id = 'chatbot-panel';
        panel.className = 'chatbot-panel';

        panel.innerHTML = `
            <div class="chatbot-header">
                <div class="chatbot-header-left">
                    <i class="fas fa-robot chatbot-avatar"></i>
                    <div>
                        <div class="chatbot-title">Survey Analyst</div>
                        <div class="chatbot-subtitle">AI-powered data insights</div>
                    </div>
                </div>
                <div class="chatbot-header-actions">
                    <button class="chatbot-header-btn" id="chatbot-export" title="Export transcript">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="chatbot-header-btn" id="chatbot-new-chat" title="New conversation">
                        <i class="fas fa-plus"></i>
                    </button>
                    <button class="chatbot-header-btn" id="chatbot-close" title="Close">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="chatbot-persona-bar">
                <label class="chatbot-persona-label"><i class="fas fa-user-tie"></i> Persona:</label>
                <select id="chatbot-persona-select" class="chatbot-persona-select">
                    <option value="analyst" ${this.persona === 'analyst' ? 'selected' : ''}>📊 Data Analyst</option>
                    <option value="executive" ${this.persona === 'executive' ? 'selected' : ''}>💼 Executive Brief</option>
                    <option value="researcher" ${this.persona === 'researcher' ? 'selected' : ''}>🔬 UX Researcher</option>
                    <option value="casual" ${this.persona === 'casual' ? 'selected' : ''}>💬 Casual Helper</option>
                </select>
            </div>
            <div class="chatbot-messages" id="chatbot-messages">
                ${this.messages.length === 0 ? this._renderWelcome() : ''}
            </div>
            <div class="chatbot-input-area">
                <div class="chatbot-input-wrapper">
                    <textarea id="chatbot-input" class="chatbot-input" placeholder="Ask about your survey data..." rows="1" maxlength="2000"></textarea>
                    <button id="chatbot-send" class="chatbot-send-btn" title="Send" disabled>
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </div>
                <div class="chatbot-footer-hint">AI answers are based on your survey data. Verify critical insights.</div>
            </div>
        `;

        document.body.appendChild(panel);

        // Render existing messages
        if (this.messages.length > 0) {
            const container = document.getElementById('chatbot-messages');
            container.innerHTML = '';
            this.messages.forEach(msg => this._appendMessage(msg.role, msg.content, msg.sources, msg.followUps));
        }

        this._bindEvents();

        // Animate in
        requestAnimationFrame(() => panel.classList.add('open'));
    },

    _renderWelcome() {
        const suggestions = this.suggestedQuestions.slice(0, 4).map(q =>
            `<button class="chatbot-suggestion" data-question="${Helpers.escapeHtml(q)}">${Helpers.escapeHtml(q)}</button>`
        ).join('');

        return `
            <div class="chatbot-welcome">
                <div class="chatbot-welcome-icon"><i class="fas fa-brain"></i></div>
                <h3>Survey Analysis Assistant</h3>
                <p>Ask me anything about your survey data, respondent feedback, themes, sentiments, and insights.</p>
                <div class="chatbot-suggestions">
                    ${suggestions}
                </div>
            </div>
        `;
    },

    _bindEvents() {
        const input = document.getElementById('chatbot-input');
        const sendBtn = document.getElementById('chatbot-send');

        // Close button
        document.getElementById('chatbot-close')?.addEventListener('click', () => this.close());

        // Export transcript
        document.getElementById('chatbot-export')?.addEventListener('click', () => this.exportTranscript());

        // Persona selector
        document.getElementById('chatbot-persona-select')?.addEventListener('change', (e) => {
            this.persona = e.target.value;
            localStorage.setItem('chatbot_persona', this.persona);
        });

        // New chat
        document.getElementById('chatbot-new-chat')?.addEventListener('click', () => {
            this.conversationId = null;
            this.messages = [];
            const container = document.getElementById('chatbot-messages');
            if (container) container.innerHTML = this._renderWelcome();
            this._bindSuggestions();
            if (input) { input.value = ''; input.style.height = 'auto'; }
            if (sendBtn) sendBtn.disabled = true;
        });

        // Input events
        input?.addEventListener('input', () => {
            // Auto-resize
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
            // Toggle send button
            if (sendBtn) sendBtn.disabled = !input.value.trim();
        });

        input?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.send();
            }
        });

        // Send button
        sendBtn?.addEventListener('click', () => this.send());

        // Suggestion buttons
        this._bindSuggestions();

        // Focus input
        setTimeout(() => input?.focus(), 200);
    },

    _bindSuggestions() {
        document.querySelectorAll('.chatbot-suggestion').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const question = e.currentTarget.dataset.question;
                const input = document.getElementById('chatbot-input');
                if (input) input.value = question;
                this.send();
            });
        });
    },

    async send() {
        const input = document.getElementById('chatbot-input');
        const message = input?.value?.trim();
        if (!message || this.isLoading) return;

        // Clear input
        input.value = '';
        input.style.height = 'auto';
        document.getElementById('chatbot-send').disabled = true;

        // Remove welcome state
        const welcome = document.querySelector('.chatbot-welcome');
        if (welcome) welcome.remove();

        // Add user message
        this.messages.push({ role: 'user', content: message });
        this._appendMessage('user', message);

        // Show typing indicator
        this.isLoading = true;
        this._showTyping();

        try {
            const result = await API.insights.chatQuery(
                this.surveyId,
                message,
                this.conversationId,
                this.persona
            );

            // Store conversation ID for continuity
            this.conversationId = result.conversation_id;

            // Remove typing indicator
            this._hideTyping();

            // Add assistant message
            const answer = result.answer || "I couldn't analyze that. Please try again.";
            const sources = result.sources || [];
            const followUps = result.follow_up_questions || [];

            this.messages.push({ role: 'assistant', content: answer, sources, followUps });
            this._appendMessage('assistant', answer, sources, followUps);

        } catch (err) {
            this._hideTyping();
            const errorMsg = "Sorry, I encountered an error analyzing your survey data. Please try again.";
            this.messages.push({ role: 'assistant', content: errorMsg });
            this._appendMessage('assistant', errorMsg);
            console.error('Chatbot error:', err);
        } finally {
            this.isLoading = false;
        }
    },

    _appendMessage(role, content, sources = [], followUps = []) {
        const container = document.getElementById('chatbot-messages');
        if (!container) return;

        const msgEl = document.createElement('div');
        msgEl.className = `chatbot-msg chatbot-msg-${role}`;

        if (role === 'user') {
            msgEl.innerHTML = `
                <div class="chatbot-msg-bubble chatbot-msg-user-bubble">
                    ${Helpers.escapeHtml(content)}
                </div>
            `;
        } else {
            // Format markdown-ish content for display
            const formatted = this._formatAnswer(content);
            let sourcesHtml = '';
            if (sources.length > 0) {
                sourcesHtml = `
                    <div class="chatbot-sources">
                        <div class="chatbot-sources-label"><i class="fas fa-database"></i> Data sources:</div>
                        ${sources.map(s => `<span class="chatbot-source-tag">${Helpers.escapeHtml(s)}</span>`).join('')}
                    </div>
                `;
            }

            let followUpHtml = '';
            if (followUps.length > 0) {
                followUpHtml = `
                    <div class="chatbot-follow-ups">
                        ${followUps.map(q => `<button class="chatbot-follow-up-btn" data-question="${Helpers.escapeHtml(q)}">${Helpers.escapeHtml(q)}</button>`).join('')}
                    </div>
                `;
            }

            const msgIndex = this.messages.length - 1;
            const isPinned = this.messages[msgIndex]?.pinned;

            msgEl.innerHTML = `
                <div class="chatbot-msg-avatar"><i class="fas fa-robot"></i></div>
                <div class="chatbot-msg-content">
                    <div class="chatbot-msg-bubble chatbot-msg-ai-bubble">${formatted}</div>
                    <div class="chatbot-msg-actions">
                        <button class="chatbot-action-btn chatbot-pin-btn ${isPinned ? 'pinned' : ''}" data-msg-index="${msgIndex}" title="${isPinned ? 'Unpin insight' : 'Pin insight'}">
                            <i class="fas fa-thumbtack"></i>
                        </button>
                        <button class="chatbot-action-btn chatbot-copy-btn" data-msg-index="${msgIndex}" title="Copy to clipboard">
                            <i class="fas fa-copy"></i>
                        </button>
                    </div>
                    ${sourcesHtml}
                    ${followUpHtml}
                </div>
            `;

            // Bind action buttons
            setTimeout(() => {
                // Pin button
                msgEl.querySelector('.chatbot-pin-btn')?.addEventListener('click', (e) => {
                    const idx = parseInt(e.currentTarget.dataset.msgIndex);
                    this._togglePin(idx, e.currentTarget);
                });
                // Copy button
                msgEl.querySelector('.chatbot-copy-btn')?.addEventListener('click', (e) => {
                    const idx = parseInt(e.currentTarget.dataset.msgIndex);
                    const msg = this.messages[idx];
                    if (msg) {
                        navigator.clipboard.writeText(msg.content).then(() => {
                            e.currentTarget.innerHTML = '<i class="fas fa-check"></i>';
                            setTimeout(() => e.currentTarget.innerHTML = '<i class="fas fa-copy"></i>', 1500);
                        });
                    }
                });
                // Follow-up buttons
                msgEl.querySelectorAll('.chatbot-follow-up-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const question = e.currentTarget.dataset.question;
                        const input = document.getElementById('chatbot-input');
                        if (input) input.value = question;
                        this.send();
                    });
                });
            }, 0);
        }

        container.appendChild(msgEl);
        // Scroll to bottom smoothly
        container.scrollTop = container.scrollHeight;
    },

    _showTyping() {
        const container = document.getElementById('chatbot-messages');
        if (!container) return;

        const typing = document.createElement('div');
        typing.id = 'chatbot-typing';
        typing.className = 'chatbot-msg chatbot-msg-assistant';
        typing.innerHTML = `
            <div class="chatbot-msg-avatar"><i class="fas fa-robot"></i></div>
            <div class="chatbot-msg-content">
                <div class="chatbot-typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        container.appendChild(typing);
        container.scrollTop = container.scrollHeight;
    },

    _hideTyping() {
        document.getElementById('chatbot-typing')?.remove();
    },

    _formatAnswer(text) {
        if (!text) return '';
        // Simple markdown-like formatting
        let html = Helpers.escapeHtml(text);
        // Bold: **text**
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Italic: *text*
        html = html.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
        // Bullet lists: - item or * item
        html = html.replace(/^[\-\*]\s+(.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
        // Numbered lists: 1. item
        html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');
        // Line breaks
        html = html.replace(/\n/g, '<br>');
        // Clean up double <br> around lists
        html = html.replace(/<br><ul>/g, '<ul>');
        html = html.replace(/<\/ul><br>/g, '</ul>');
        return html;
    },

    // ── Export Transcript ──
    exportTranscript() {
        if (this.messages.length === 0) {
            if (typeof Helpers !== 'undefined' && Helpers.toast) {
                Helpers.toast('No Messages', 'Start a conversation first to export.', 'warning');
            }
            return;
        }

        const now = new Date();
        const dateStr = now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        let md = `# Survey Analysis Chat Transcript\n`;
        md += `**Date:** ${dateStr}\n`;
        md += `**Persona:** ${this.persona}\n`;
        md += `**Conversation ID:** ${this.conversationId || 'N/A'}\n\n`;
        md += `---\n\n`;

        this.messages.forEach(msg => {
            if (msg.role === 'user') {
                md += `### 🧑 You\n${msg.content}\n\n`;
            } else {
                md += `### 🤖 AI Analyst\n${msg.content}\n\n`;
                if (msg.sources && msg.sources.length > 0) {
                    md += `**Sources:** ${msg.sources.join(', ')}\n\n`;
                }
            }
        });

        // Append pinned insights section
        const pinned = this.messages.filter(m => m.pinned);
        if (pinned.length > 0) {
            md += `---\n\n## 📌 Pinned Insights\n\n`;
            pinned.forEach((msg, i) => {
                md += `${i + 1}. ${msg.content.substring(0, 200)}${msg.content.length > 200 ? '...' : ''}\n\n`;
            });
        }

        // Download as markdown
        const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat-transcript-${now.toISOString().slice(0, 10)}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        if (typeof Helpers !== 'undefined' && Helpers.toast) {
            Helpers.toast('Exported', 'Transcript downloaded as Markdown.', 'success');
        }
    },

    // ── Pin/Bookmark Insights ──
    _togglePin(msgIndex, btnEl) {
        if (msgIndex < 0 || msgIndex >= this.messages.length) return;
        const msg = this.messages[msgIndex];
        msg.pinned = !msg.pinned;

        if (btnEl) {
            btnEl.classList.toggle('pinned', msg.pinned);
            btnEl.title = msg.pinned ? 'Unpin insight' : 'Pin insight';
        }

        // Save pinned insights to localStorage
        this._savePinnedInsights();

        if (typeof Helpers !== 'undefined' && Helpers.toast) {
            Helpers.toast(msg.pinned ? 'Pinned' : 'Unpinned', msg.pinned ? 'Insight bookmarked.' : 'Bookmark removed.', 'success', 2000);
        }
    },

    _savePinnedInsights() {
        const pinned = this.messages
            .filter(m => m.pinned && m.role === 'assistant')
            .map(m => ({ content: m.content, sources: m.sources || [], timestamp: new Date().toISOString() }));
        const key = `pinned_insights_${this.surveyId}`;
        localStorage.setItem(key, JSON.stringify(pinned));
    },

    getPinnedInsights() {
        const key = `pinned_insights_${this.surveyId}`;
        try { return JSON.parse(localStorage.getItem(key) || '[]'); } catch { return []; }
    },

    destroy() {
        document.getElementById('chatbot-panel')?.remove();
        document.getElementById('chatbot-toggle-btn')?.remove();
        this.isOpen = false;
        this.messages = [];
        this.conversationId = null;
    }
};
