/*
 * stickers_render.js
 * Универсальный рендер стикеров: находит текст [sticker:cat/file.webp]
 * и заменяет его на картинку. Работает на всех страницах,
 * включая динамически добавленные сообщения.
 */

(function () {
    "use strict";

    var RE = /^\[sticker:([a-zA-Z0-9_-]+)\/([a-zA-Z0-9._-]+)\]$/;

    function convert(root) {
        if (!root || !root.body && root !== document.body && !root.querySelectorAll) return;
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
        var node;
        var targets = [];
        while ((node = walker.nextNode())) {
            // не трогаем поля ввода и скрипты
            var parent = node.parentNode;
            if (!parent) continue;
            var tag = (parent.nodeName || "").toLowerCase();
            if (tag === "script" || tag === "style" || tag === "textarea" || tag === "input") continue;
            var t = (node.textContent || "").trim();
            if (t && t.length < 80 && RE.test(t)) targets.push(node);
        }
        targets.forEach(function (n) {
            var m = RE.exec(n.textContent.trim());
            if (!m) return;
            var img = document.createElement("img");
            img.className = "bb-sticker";
            img.src = "/static/stickers/" + encodeURIComponent(m[1]) + "/" + encodeURIComponent(m[2]);
            img.alt = "стикер";
            img.title = m[2];
            n.parentNode.replaceChild(img, n);
        });
    }

    var timer = null;
    function schedule() {
        clearTimeout(timer);
        timer = setTimeout(function () { convert(document.body); }, 80);
    }

    document.addEventListener("DOMContentLoaded", function () {
        convert(document.body);

        if ("MutationObserver" in window) {
            var mo = new MutationObserver(function (muts) {
                for (var i = 0; i < muts.length; i++) {
                    if (muts[i].addedNodes && muts[i].addedNodes.length) {
                        schedule();
                        return;
                    }
                }
            });
            mo.observe(document.body, { childList: true, subtree: true });
        }

        // страховка для страниц, где текст обновляется на месте
        setInterval(function () { convert(document.body); }, 3000);
    });
})();
