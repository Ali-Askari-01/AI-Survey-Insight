/**
 * Feedback Widget & Analytics Tracker
 * ═══════════════════════════════════════════════════════════════
 * Provides user feedback collection and website analytics tracking
 * - User feedback modal for software feedback
 * - Respondent experience tracker (30-second max)
 * - Page view and user behavior analytics
 * - Feature usage tracking
 */

class FeedbackAnalytics {
    constructor() {
        this.sessionId = this.getOrCreateSessionId();
        this.pageStartTime = Date.now();
        this.feedbackModalOpen = false;
        this.experienceWidgetShown = false;
        
        this.init();
    }

    init() {
        this.trackPageView();
        this.createFeedbackWidget();
        this.setupEventListeners();
        this.setupBeforeUnloadTracking();
    }

    getOrCreateSessionId() {
        let sessionId = localStorage.getItem('analytics_session_id');
        if (!sessionId) {
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('analytics_session_id', sessionId);
        }
        return sessionId;
    }

    async trackPageView() {
        try {
            const pageData = {
                page_url: window.location.href,
                page_title: document.title,
                referrer: document.referrer,
                time_on_page: 0,
                exit_page: false,
                conversion_event: null
            };

            const response = await fetch('/api/track/page-view', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.getAuthToken()
                },
                body: JSON.stringify(pageData)
            });

            if (response.ok) {
                const result = await response.json();
                if (result.session_id) {
                    this.sessionId = result.session_id;
                }
            }
        } catch (error) {
            console.warn('Analytics tracking failed:', error);
        }
    }

    async trackFeatureUsage(featureName, action, surveyId = null, metadata = {}, sessionDuration = null) {
        try {
            const usageData = {
                feature_name: featureName,
                action: action,
                survey_id: surveyId,
                metadata: metadata,
                session_duration: sessionDuration,
                success: true
            };

            await fetch('/api/track/feature-usage', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.getAuthToken()
                },
                body: JSON.stringify(usageData)
            });
        } catch (error) {
            console.warn('Feature usage tracking failed:', error);
        }
    }

    async trackConversionEvent(eventName) {
        try {
            const pageData = {
                page_url: window.location.href,
                page_title: document.title,
                referrer: document.referrer,
                time_on_page: Date.now() - this.pageStartTime,
                exit_page: false,
                conversion_event: eventName
            };

            await fetch('/api/track/page-view', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.getAuthToken()
                },
                body: JSON.stringify(pageData)
            });
        } catch (error) {
            console.warn('Conversion tracking failed:', error);
        }
    }

    createFeedbackWidget() {
        // Create feedback widget HTML
        const widgetHTML = `
            <div class="feedback-widget">
                <button class="feedback-trigger" onclick="feedbackAnalytics.openFeedbackModal()">
                    <i class="fas fa-comment-dots"></i>
                </button>
            </div>

            <div class="feedback-modal" id="feedbackModal">
                <div class="feedback-modal-content">
                    <div class="feedback-header">
                        <h3><i class="fas fa-heart" style="color: var(--accent-gold); margin-right: 8px;"></i>We'd Love Your Feedback</h3>
                        <button class="feedback-close" onclick="feedbackAnalytics.closeFeedbackModal()">&times;</button>
                    </div>

                    <div id="feedbackForm">
                        <div class="feedback-form">
                            <div class="form-group">
                                <label>What type of feedback do you have?</label>
                                <div class="feedback-types">
                                    <div class="feedback-type" data-type="general">
                                        <i class="fas fa-comment"></i>
                                        <span>General</span>
                                    </div>
                                    <div class="feedback-type" data-type="bug">
                                        <i class="fas fa-bug"></i>
                                        <span>Bug Report</span>
                                    </div>
                                    <div class="feedback-type" data-type="feature_request">
                                        <i class="fas fa-lightbulb"></i>
                                        <span>Feature Idea</span>
                                    </div>
                                    <div class="feedback-type" data-type="improvement">
                                        <i class="fas fa-arrow-up"></i>
                                        <span>Improvement</span>
                                    </div>
                                </div>
                            </div>

                            <div class="form-group">
                                <label>How would you rate your overall experience?</label>
                                <div class="star-rating" id="overallRating">
                                    <span class="star" data-rating="1">★</span>
                                    <span class="star" data-rating="2">★</span>
                                    <span class="star" data-rating="3">★</span>
                                    <span class="star" data-rating="4">★</span>
                                    <span class="star" data-rating="5">★</span>
                                </div>
                            </div>

                            <div class="form-group">
                                <label for="feedbackTitle">Title (optional)</label>
                                <input type="text" id="feedbackTitle" placeholder="Brief summary of your feedback">
                            </div>

                            <div class="form-group">
                                <label for="feedbackDescription">Tell us more *</label>
                                <textarea id="feedbackDescription" placeholder="Please describe your feedback in detail. Your insights help us improve!" required></textarea>
                            </div>

                            <div class="form-group">
                                <label for="featureArea">Which area does this relate to?</label>
                                <select id="featureArea">
                                    <option value="">Select an area</option>
                                    <option value="survey_creation">Survey Creation</option>
                                    <option value="interview_experience">Interview Experience</option>
                                    <option value="ai_insights">AI Insights</option>
                                    <option value="dashboard">Dashboard</option>
                                    <option value="reports">Reports & Analytics</option>
                                    <option value="authentication">Login/Authentication</option>
                                    <option value="mobile_experience">Mobile Experience</option>
                                    <option value="performance">Performance</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>

                            <div class="form-group">
                                <label for="priority">How important is this to you?</label>
                                <select id="priority">
                                    <option value="low">Low - Nice to have</option>
                                    <option value="medium" selected>Medium - Would improve my experience</option>
                                    <option value="high">High - Significantly impacts my workflow</option>
                                    <option value="critical">Critical - Preventing me from using the software</option>
                                </select>
                            </div>
                        </div>

                        <div class="feedback-actions">
                            <button type="button" class="btn-feedback-cancel" onclick="feedbackAnalytics.closeFeedbackModal()">Cancel</button>
                            <button type="button" class="btn-feedback-submit" onclick="feedbackAnalytics.submitFeedback()">
                                <i class="fas fa-paper-plane"></i>
                                Send Feedback
                            </button>
                        </div>
                    </div>

                    <div id="feedbackSuccess" style="display: none;">
                        <div class="feedback-success">
                            <i class="fas fa-check-circle"></i>
                            <h4>Thank you for your feedback!</h4>
                            <p>Your input helps us build a better product for everyone.</p>
                            <button class="btn-feedback-submit" onclick="feedbackAnalytics.closeFeedbackModal()">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', widgetHTML);
        this.setupFeedbackEventListeners();
    }

    setupFeedbackEventListeners() {
        // Feedback type selection
        document.querySelectorAll('.feedback-type').forEach(type => {
            type.addEventListener('click', () => {
                document.querySelectorAll('.feedback-type').forEach(t => t.classList.remove('selected'));
                type.classList.add('selected');
            });
        });

        // Star rating
        document.querySelectorAll('#overallRating .star').forEach(star => {
            star.addEventListener('click', () => {
                const rating = parseInt(star.dataset.rating);
                document.querySelectorAll('#overallRating .star').forEach((s, index) => {
                    s.classList.toggle('active', index < rating);
                });
            });
        });

        // Close modal on backdrop click
        document.getElementById('feedbackModal').addEventListener('click', (e) => {
            if (e.target.id === 'feedbackModal') {
                this.closeFeedbackModal();
            }
        });
    }

    setupEventListeners() {
        // Track clicks on important elements
        document.addEventListener('click', (e) => {
            // Track button clicks
            if (e.target.matches('.btn, button')) {
                const buttonText = e.target.textContent?.trim() || e.target.className;
                this.trackFeatureUsage('button_click', 'click', null, { button_text: buttonText });
            }

            // Track navigation clicks
            if (e.target.matches('a') || e.target.closest('a')) {
                const link = e.target.closest('a') || e.target;
                this.trackFeatureUsage('navigation', 'link_click', null, { url: link.href });
            }
        });

        // Track form submissions
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form.id) {
                this.trackFeatureUsage('form_submission', 'submit', null, { form_id: form.id });
            }
        });
    }

    setupBeforeUnloadTracking() {
        window.addEventListener('beforeunload', () => {
            const timeOnPage = Date.now() - this.pageStartTime;
            navigator.sendBeacon('/api/track/page-view', JSON.stringify({
                page_url: window.location.href,
                page_title: document.title,
                referrer: document.referrer,
                time_on_page: timeOnPage,
                exit_page: true,
                conversion_event: null
            }));
        });
    }

    openFeedbackModal() {
        const modal = document.getElementById('feedbackModal');
        modal.classList.add('active');
        this.feedbackModalOpen = true;
        this.trackFeatureUsage('feedback_widget', 'open', null);
    }

    closeFeedbackModal() {
        const modal = document.getElementById('feedbackModal');
        modal.classList.remove('active');
        this.feedbackModalOpen = false;
        
        // Reset form
        document.getElementById('feedbackForm').style.display = 'block';
        document.getElementById('feedbackSuccess').style.display = 'none';
        document.getElementById('feedbackDescription').value = '';
        document.getElementById('feedbackTitle').value = '';
        document.querySelectorAll('.feedback-type').forEach(t => t.classList.remove('selected'));
        document.querySelectorAll('#overallRating .star').forEach(s => s.classList.remove('active'));
    }

    async submitFeedback() {
        const description = document.getElementById('feedbackDescription').value.trim();
        if (!description) {
            alert('Please provide your feedback description.');
            return;
        }

        const submitButton = document.querySelector('.btn-feedback-submit');
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';

        try {
            const feedbackData = {
                feedback_type: document.querySelector('.feedback-type.selected')?.dataset.type || 'general',
                rating: document.querySelectorAll('#overallRating .star.active').length || null,
                title: document.getElementById('feedbackTitle').value || null,
                description: description,
                feature_area: document.getElementById('featureArea').value || null,
                priority: document.getElementById('priority').value,
                browser_info: navigator.userAgent,
                url_context: window.location.href
            };

            const response = await fetch('/api/feedback/user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.getAuthToken()
                },
                body: JSON.stringify(feedbackData)
            });

            if (response.ok) {
                document.getElementById('feedbackForm').style.display = 'none';
                document.getElementById('feedbackSuccess').style.display = 'block';
                this.trackFeatureUsage('feedback_widget', 'submit_success', null, { feedback_type: feedbackData.feedback_type });
            } else {
                throw new Error('Failed to submit feedback');
            }
        } catch (error) {
            console.error('Feedback submission failed:', error);
            alert('Failed to submit feedback. Please try again.');
            this.trackFeatureUsage('feedback_widget', 'submit_error', null);
        } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-paper-plane"></i> Send Feedback';
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // RESPONDENT EXPERIENCE TRACKER (30-second max)
    // ═══════════════════════════════════════════════════════════════

    showExperienceWidget(sessionId, surveyId, delayMs = 2000) {
        if (this.experienceWidgetShown) return;
        
        setTimeout(() => {
            this.createExperienceWidget(sessionId, surveyId);
            this.experienceWidgetShown = true;
        }, delayMs);
    }

    createExperienceWidget(sessionId, surveyId) {
        const widgetHTML = `
            <div class="experience-widget" id="experienceWidget">
                <h4>How was your experience? <span style="font-size: 0.8rem; color: var(--text-tertiary);">(30 sec)</span></h4>
                
                <div class="experience-quick-rating">
                    <button class="quick-rating-btn" data-rating="1">😞</button>
                    <button class="quick-rating-btn" data-rating="2">😐</button>
                    <button class="quick-rating-btn" data-rating="3">🙂</button>
                    <button class="quick-rating-btn" data-rating="4">😊</button>
                    <button class="quick-rating-btn" data-rating="5">😍</button>
                </div>

                <textarea class="experience-comment" placeholder="Quick feedback (optional)..."></textarea>

                <div class="experience-actions">
                    <button class="btn-experience btn-experience-skip" onclick="feedbackAnalytics.closeExperienceWidget()">Skip</button>
                    <button class="btn-experience btn-experience-submit" onclick="feedbackAnalytics.submitExperience('${sessionId}', ${surveyId})">Submit</button>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', widgetHTML);
        
        // Show widget
        requestAnimationFrame(() => {
            document.getElementById('experienceWidget').classList.add('show');
        });

        // Setup rating buttons
        document.querySelectorAll('.quick-rating-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.quick-rating-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
            });
        });

        // Auto-hide after 30 seconds
        setTimeout(() => {
            this.closeExperienceWidget();
        }, 30000);
    }

    async submitExperience(sessionId, surveyId) {
        const rating = document.querySelector('.quick-rating-btn.selected')?.dataset.rating || null;
        const comment = document.querySelector('.experience-comment').value.trim();

        try {
            const experienceData = {
                session_id: sessionId,
                survey_id: parseInt(surveyId),
                overall_rating: rating ? parseInt(rating) : null,
                quick_feedback: comment || null,
                completion_time: Date.now() - this.pageStartTime,
                channel_used: this.getChannelFromUrl()
            };

            const response = await fetch('/api/feedback/respondent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.getAuthToken()
                },
                body: JSON.stringify(experienceData)
            });

            if (response.ok) {
                this.showExperienceThankYou();
                this.trackFeatureUsage('experience_widget', 'submit_success', surveyId);
            } else {
                throw new Error('Failed to submit experience');
            }
        } catch (error) {
            console.error('Experience submission failed:', error);
            this.closeExperienceWidget();
        }
    }

    showExperienceThankYou() {
        const widget = document.getElementById('experienceWidget');
        if (widget) {
            widget.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <i class="fas fa-check-circle" style="color: var(--accent-gold); font-size: 2rem; margin-bottom: 8px;"></i>
                    <p style="color: var(--text-primary); margin: 0;">Thank you for your feedback!</p>
                </div>
            `;
            setTimeout(() => this.closeExperienceWidget(), 2000);
        }
    }

    closeExperienceWidget() {
        const widget = document.getElementById('experienceWidget');
        if (widget) {
            widget.classList.remove('show');
            setTimeout(() => widget.remove(), 300);
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // UTILITY METHODS
    // ═══════════════════════════════════════════════════════════════

    getAuthToken() {
        const token = localStorage.getItem('token') || sessionStorage.getItem('token');
        return token ? `Bearer ${token}` : '';
    }

    getChannelFromUrl() {
        const path = window.location.pathname;
        if (path.includes('survey-form')) return 'web';
        if (path.includes('survey-chat')) return 'chat';
        if (path.includes('survey-audio')) return 'audio';
        return 'web';
    }
}

// Initialize analytics when page loads
let feedbackAnalytics;
document.addEventListener('DOMContentLoaded', () => {
    feedbackAnalytics = new FeedbackAnalytics();
    
    // Add global tracking functions for easy access
    window.trackConversion = (event) => feedbackAnalytics.trackConversionEvent(event);
    window.trackFeature = (feature, action, metadata = {}) => feedbackAnalytics.trackFeatureUsage(feature, action, null, metadata);
    window.showExperienceWidget = (sessionId, surveyId) => feedbackAnalytics.showExperienceWidget(sessionId, surveyId);
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FeedbackAnalytics;
}