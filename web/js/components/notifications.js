/**
 * Notifications Component — Toast alerts, notification panel, badges
 * Feature 5: Continuous Improvement & Adaptive Feedback
 */
const NotificationsComponent = {
    notifications: [],
    unreadCount: 0,
    pollInterval: null,

    async init() {
        await this.loadNotifications();
        this.bindEvents();
        this.startPolling();
    },

    async loadNotifications() {
        try {
            const [notifs, countData] = await Promise.all([
                API.notifications.list(),
                API.notifications.getUnreadCount()
            ]);
            this.notifications = notifs;
            this.unreadCount = countData.count;
            this.updateBadge();
        } catch (e) { console.error('Failed to load notifications:', e); }
    },

    updateBadge() {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            badge.textContent = this.unreadCount;
            badge.style.display = this.unreadCount > 0 ? 'flex' : 'none';
        }
    },

    bindEvents() {
        const btn = document.getElementById('notification-btn');
        const panel = document.getElementById('notification-panel');
        const markAll = document.getElementById('mark-all-read');

        btn?.addEventListener('click', (e) => {
            e.stopPropagation();
            panel.hidden = !panel.hidden;
            if (!panel.hidden) this.renderPanel();
        });

        markAll?.addEventListener('click', async () => {
            await API.notifications.markAllRead();
            this.notifications.forEach(n => n.is_read = 1);
            this.unreadCount = 0;
            this.updateBadge();
            this.renderPanel();
        });

        document.addEventListener('click', (e) => {
            if (!panel?.contains(e.target) && !btn?.contains(e.target)) {
                panel.hidden = true;
            }
        });
    },

    renderPanel() {
        const list = document.getElementById('notification-list');
        if (!list) return;

        if (this.notifications.length === 0) {
            list.innerHTML = '<div class="empty-state"><i class="fas fa-bell"></i><p>No notifications</p></div>';
            return;
        }

        list.innerHTML = this.notifications.map(n => {
            const info = Helpers.severityInfo(n.severity);
            return `
                <div class="notif-item ${n.is_read ? '' : 'unread'} severity-${n.severity}" data-id="${n.id}">
                    <div class="notif-icon" style="background: ${info.bg}; color: ${info.color}">
                        <i class="fas ${info.icon}"></i>
                    </div>
                    <div class="notif-content">
                        <div class="notif-title">${Helpers.escapeHtml(n.title)}</div>
                        <div class="notif-message">${Helpers.escapeHtml(n.message || '')}</div>
                        <div class="notif-time">${Helpers.timeAgo(n.created_at)}</div>
                    </div>
                </div>
            `;
        }).join('');

        list.querySelectorAll('.notif-item').forEach(item => {
            item.addEventListener('click', async () => {
                const id = item.dataset.id;
                await API.notifications.markRead(id);
                item.classList.remove('unread');
                this.unreadCount = Math.max(0, this.unreadCount - 1);
                this.updateBadge();
            });
        });
    },

    /**
     * Show a toast for critical notifications
     */
    showCriticalAlerts() {
        const critical = this.notifications.filter(n => !n.is_read && (n.severity === 'critical' || n.severity === 'high'));
        critical.slice(0, 2).forEach(n => {
            const type = n.severity === 'critical' ? 'danger' : 'warning';
            Helpers.toast(n.title, n.message, type, 6000);
        });
    },

    startPolling() {
        this.pollInterval = setInterval(async () => {
            try {
                const countData = await API.notifications.getUnreadCount();
                if (countData.count > this.unreadCount) {
                    this.unreadCount = countData.count;
                    this.updateBadge();
                    await this.loadNotifications();
                    this.showCriticalAlerts();
                }
            } catch (e) { /* silent */ }
        }, 30000);
    },

    destroy() {
        if (this.pollInterval) clearInterval(this.pollInterval);
    }
};
