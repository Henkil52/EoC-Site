/*
 * notifications.js — колокол уведомлений о достижениях
 */

(function () {
    "use strict";

    var btn = document.getElementById("bellBtn");
    if (!btn) return;

    var panel = document.getElementById("bellPanel");
    var list = document.getElementById("bellList");
    var badge = document.getElementById("bellBadge");
    var readAll = document.getElementById("bellReadAll");

    function esc(s) {
        var d = document.createElement("div");
        d.textContent = (s == null ? "" : String(s));
        return d.innerHTML;
    }

    function render(items) {
        list.innerHTML = "";
        if (!items.length) {
            list.innerHTML = '<div class="bell-empty">Уведомлений пока нет</div>';
            return;
        }
        items.forEach(function (n) {
            var el = document.createElement("div");
            el.className = "bell-item" + (n.read ? "" : " bell-unread");
            el.innerHTML =
                '<img class="bell-sticker" src="' + esc(n.sticker) + '" alt="">' +
                '<div class="bell-body">' +
                '<div class="bell-title">🏆 ' + esc(n.title) + '</div>' +
                '<div class="bell-time">' + esc(n.time) + '</div>' +
                '</div>';
            list.appendChild(el);
        });
    }

    function load(forceRender) {
        fetch("/achievements/api/notifications", { headers: { "Accept": "application/json" } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var items = (data && data.notifications) || [];
                var unread = 0;
                items.forEach(function (i) { if (!i.read) unread++; });
                badge.hidden = (unread === 0);
                badge.textContent = unread > 99 ? "99+" : unread;
                var cntEl = document.getElementById("bellCount");
                if (cntEl) cntEl.textContent = unread ? "(" + unread + ")" : "";
                if (forceRender || !panel.hidden) render(items);
            })
            .catch(function () {});
    }

    btn.addEventListener("click", function (e) {
        e.stopPropagation();
        panel.hidden = !panel.hidden;
        if (!panel.hidden) load(true);
    });

    readAll.addEventListener("click", function (e) {
        e.stopPropagation();
        fetch("/achievements/api/notifications/read", { method: "POST" })
            .then(function () { load(true); })
            .catch(function () {});
    });

    document.addEventListener("click", function (e) {
        if (!panel.hidden && !panel.contains(e.target) && e.target !== btn) {
            panel.hidden = true;
        }
    });

    setInterval(function () { load(false); }, 30000);
    load(false);
})();
