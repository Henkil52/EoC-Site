/*
 * theme.js
 * Переключение тем: тёмная / серая / светлая.
 * Сохраняется в localStorage и применяется мгновенно.
 */

const THEMES = ['dark', 'gray', 'light'];
const THEME_ICONS = { dark: '🌙', gray: '🌫️', light: '☀️' };

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('site_theme', theme);

    const icon = document.getElementById('theme-icon');
    if (icon) icon.textContent = THEME_ICONS[theme] || '🌙';
}

function cycleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
    applyTheme(next);
}

document.addEventListener('DOMContentLoaded', function () {
    const saved = localStorage.getItem('site_theme') || 'dark';
    applyTheme(saved);
});

/* ── Дропдаун профиля (JS) ───────────────────────────────── */
function toggleProfileMenu(e) {
    e.stopPropagation();
    var dd = document.getElementById('profileDropdown');
    if (dd) dd.classList.toggle('open');
}

document.addEventListener('click', function (e) {
    var dd = document.getElementById('profileDropdown');
    if (dd && !dd.contains(e.target)) dd.classList.remove('open');
});


/* ── Автообновление бейджа непрочитанных сообщений ── */
(function () {
    function refreshUnread() {
        fetch('/messages/api/unread')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (d) {
                if (!d) return;
                var el = document.getElementById('unread-count');
                if (el) {
                    el.textContent = d.count;
                    el.style.display = d.count > 0 ? 'inline-flex' : 'none';
                }
            })
            .catch(function () {});
    }

    if (document.getElementById('unread-count')) {
        setInterval(refreshUnread, 20000);
    }
})();
