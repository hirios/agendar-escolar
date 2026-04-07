/**
 * notifications.js — Componente Alpine.js para o sininho de notificações
 */

function notificationBell() {
  return {
    open: false,
    count: 0,
    notifications: [],

    async init() {
      await this.load();
      // Polling a cada 60s
      setInterval(() => this.load(), 60_000);
    },

    async load() {
      try {
        const res = await fetch('/api/v1/notifications/unread');
        const data = await res.json();
        this.count = data.count;
        this.notifications = data.notifications || [];
      } catch (_) {}
    },

    toggle() {
      this.open = !this.open;
    },

    async markAllRead() {
      try {
        await fetch('/api/v1/notifications/mark-read', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() },
        });
        this.count = 0;
        this.notifications = this.notifications.map(n => ({ ...n, is_read: true }));
      } catch (_) {}
    },
  };
}
