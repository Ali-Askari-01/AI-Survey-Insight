/**
 * Helper Utilities — Common functions used across components
 */
const Helpers = {
    /**
     * Format a timestamp to relative time (e.g., "2 hours ago")
     */
    timeAgo(date) {
        const now = new Date();
        const past = new Date(date);
        const seconds = Math.floor((now - past) / 1000);

        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
        return past.toLocaleDateString();
    },

    /**
     * Get sentiment badge class
     */
    sentimentBadge(sentiment) {
        const map = {
            positive: { cls: 'badge-positive', label: 'Positive' },
            negative: { cls: 'badge-negative', label: 'Negative' },
            neutral:  { cls: 'badge-neutral',  label: 'Neutral'  },
            mixed:    { cls: 'badge-mixed',    label: 'Mixed'    }
        };
        const info = map[sentiment] || map.neutral;
        return `<span class="badge ${info.cls}">${info.label}</span>`;
    },

    /**
     * Get sentiment color
     */
    sentimentColor(score) {
        if (score < -0.5) return '#ef4444';
        if (score < -0.2) return '#f97316';
        if (score < 0.2) return '#eab308';
        if (score < 0.5) return '#84cc16';
        return '#22c55e';
    },

    /**
     * Get sentiment background for heatmap
     */
    sentimentHeatColor(score) {
        if (score < -0.5) return 'rgba(239, 68, 68, 0.8)';
        if (score < -0.2) return 'rgba(249, 115, 22, 0.6)';
        if (score < 0.2) return 'rgba(234, 179, 8, 0.4)';
        if (score < 0.5) return 'rgba(132, 204, 22, 0.5)';
        return 'rgba(34, 197, 94, 0.7)';
    },

    /**
     * Get confidence class
     */
    confidenceClass(score) {
        if (score >= 0.8) return 'high';
        if (score >= 0.5) return 'medium';
        return 'low';
    },

    /**
     * Get severity icon and color
     */
    severityInfo(severity) {
        const map = {
            critical: { icon: 'fa-circle-exclamation', color: 'var(--danger)', bg: 'var(--danger-bg)' },
            high: { icon: 'fa-triangle-exclamation', color: 'var(--warning)', bg: 'var(--warning-bg)' },
            medium: { icon: 'fa-info-circle', color: 'var(--info)', bg: 'var(--info-bg)' },
            low: { icon: 'fa-check-circle', color: 'var(--success)', bg: 'var(--success-bg)' },
        };
        return map[severity] || map.low;
    },

    /**
     * Show a toast notification
     */
    toast(title, message = '', type = 'info', duration = 4000) {
        const container = document.getElementById('toast-container');
        const icons = {
            success: 'fa-check-circle',
            warning: 'fa-triangle-exclamation',
            danger: 'fa-circle-exclamation',
            info: 'fa-info-circle'
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-icon"><i class="fas ${icons[type] || icons.info}"></i></div>
            <div class="toast-content">
                <div class="toast-title">${Helpers.escapeHtml(title)}</div>
                ${message ? `<div class="toast-message">${Helpers.escapeHtml(message)}</div>` : ''}
            </div>
            <button class="toast-close" aria-label="Dismiss"><i class="fas fa-times"></i></button>
        `;

        toast.querySelector('.toast-close').addEventListener('click', () => removeToast(toast));
        container.appendChild(toast);

        function removeToast(el) {
            el.classList.add('removing');
            setTimeout(() => el.remove(), 300);
        }

        if (duration > 0) {
            setTimeout(() => removeToast(toast), duration);
        }
    },

    /**
     * Open the global modal
     */
    openModal(title, bodyHTML, footerHTML = '') {
        const overlay = document.getElementById('modal-overlay');
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-body').innerHTML = bodyHTML;
        document.getElementById('modal-footer').innerHTML = footerHTML;
        overlay.classList.add('active');
    },

    closeModal() {
        document.getElementById('modal-overlay').classList.remove('active');
    },

    /**
     * Generate a confidence bar HTML
     */
    confidenceBar(score) {
        const pct = Math.round(score * 100);
        const cls = this.confidenceClass(score);
        return `
            <div class="confidence-bar">
                <div class="confidence-bar-track">
                    <div class="confidence-bar-fill ${cls}" style="width: ${pct}%"></div>
                </div>
                <span class="body-xs text-bold">${pct}%</span>
            </div>
        `;
    },

    /**
     * Download data as CSV
     */
    downloadCSV(rows, filename) {
        const csv = rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
    },

    /**
     * Debounce function
     */
    debounce(fn, delay = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    /**
     * Generate unique ID
     */
    uid() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
    },

    /**
     * Format number with locale
     */
    formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    },

    /**
     * Percentage label
     */
    pct(value) {
        return `${Math.round(value * 100)}%`;
    },

    /**
     * Show a full-page or container loading overlay
     * @param {string|HTMLElement} target - 'page' for full-page, or a container element
     * @param {string} message - Loading message
     */
    showLoading(target = 'page', message = 'Loading...') {
        const id = 'loading-overlay-' + (typeof target === 'string' ? target : target.id || 'el');
        if (document.getElementById(id)) return; // already showing

        const overlay = document.createElement('div');
        overlay.id = id;
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-overlay-content">
                <div class="spinner"></div>
                <p class="loading-text">${this.escapeHtml(message)}</p>
            </div>
        `;

        if (target === 'page') {
            overlay.style.cssText = 'position:fixed;inset:0;z-index:9000;background:rgba(255,255,255,0.85);display:flex;align-items:center;justify-content:center;backdrop-filter:blur(2px)';
            document.body.appendChild(overlay);
        } else if (target instanceof HTMLElement) {
            overlay.style.cssText = 'position:absolute;inset:0;z-index:10;background:rgba(255,255,255,0.85);display:flex;align-items:center;justify-content:center;border-radius:inherit';
            target.style.position = 'relative';
            target.appendChild(overlay);
        }
    },

    hideLoading(target = 'page') {
        const id = 'loading-overlay-' + (typeof target === 'string' ? target : target.id || 'el');
        document.getElementById(id)?.remove();
    },

    /**
     * Set a button to loading state — returns a reset function
     * @param {HTMLElement} btn - The button element
     * @param {string} text - Loading text
     * @returns {Function} Call to reset the button
     */
    btnLoading(btn, text = 'Loading...') {
        if (!btn) return () => {};
        const original = btn.innerHTML;
        const wasDisabled = btn.disabled;
        btn.disabled = true;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${this.escapeHtml(text)}`;
        btn.classList.add('btn-loading');
        return () => {
            btn.disabled = wasDisabled;
            btn.innerHTML = original;
            btn.classList.remove('btn-loading');
        };
    },

    /**
     * Render a skeleton placeholder
     * @param {number} lines - Number of skeleton lines
     * @param {string} style - 'text', 'card', 'stat'
     */
    skeleton(lines = 3, style = 'text') {
        if (style === 'stat') {
            return `<div class="skeleton-stat"><div class="skeleton-line" style="width:60%;height:28px;margin:0 auto 8px"></div><div class="skeleton-line" style="width:40%;height:12px;margin:0 auto"></div></div>`;
        }
        if (style === 'card') {
            return `<div class="skeleton-card"><div class="skeleton-line" style="width:70%;height:16px;margin-bottom:12px"></div><div class="skeleton-line" style="width:100%;height:12px;margin-bottom:8px"></div><div class="skeleton-line" style="width:85%;height:12px"></div></div>`;
        }
        return Array.from({ length: lines }, (_, i) =>
            `<div class="skeleton-line" style="width:${90 - i * 10}%;height:12px;margin-bottom:8px"></div>`
        ).join('');
    }
};
