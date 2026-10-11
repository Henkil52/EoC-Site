/*
 * emoji_local.js — локальные GIF-смайлы из /static/emoji/
 * Пикер пересобирается в GIF каждый раз при открытии (ленивый рендер),
 * клик вставляет [emoji:file.gif], токен в тексте = <img>.
 */

(function () {
    "use strict";

    var LIST = null;
    var TOKEN_RE = /\[emoji:([a-zA-Z0-9_.\-]+\.gif)\]/g;
    var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, INPUT: 1, SELECT: 1, OPTION: 1 };

    /* ── Токены [emoji:x.gif] -> <img> ── */
    function convertTokens(root) {
        if (!root) return;
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
        var node, targets = [];
        while ((node = walker.nextNode())) {
            var p = node.parentNode;
            if (!p || SKIP[p.nodeName]) continue;
            if ((node.nodeValue || "").indexOf("[emoji:") !== -1) targets.push(node);
        }
        targets.forEach(function (n) {
            var text = n.nodeValue, last = 0, m;
            var frag = document.createDocumentFragment();
            TOKEN_RE.lastIndex = 0;
            while ((m = TOKEN_RE.exec(text))) {
                if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
                var img = document.createElement("img");
                img.className = "emoji-img";
                img.src = "/static/emoji/" + m[1];
                img.alt = "";
                frag.appendChild(img);
                last = m.index + m[0].length;
            }
            if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
            n.parentNode.replaceChild(frag, n);
        });
    }

    /* ── Это символ эмодзи? ── */
    function isEmojiChar(t) {
        if (!t || t.length > 3) return false;
        var cp = t.codePointAt(0);
        return (cp >= 0x1F000 && cp <= 0x1FAFF) ||
               (cp >= 0x2600 && cp <= 0x27BF) ||
               (cp >= 0x2B00 && cp <= 0x2BFF);
    }

    /* ── Похожа ли сетка на пикер (много детей-смайлов) ── */
    function gridLooksLikePicker(g) {
        var emojiKids = 0;
        for (var i = 0; i < g.children.length; i++) {
            var c = g.children[i];
            if (!c.children.length && isEmojiChar((c.textContent || "").trim())) emojiKids++;
        }
        return emojiKids >= 6 && emojiKids >= g.children.length * 0.6;
    }

    /* ── Поиск сеток пикера со старыми символами ── */
    function findPickerGrids() {
        var grids = [];
        var els = document.querySelectorAll("button, span, a, div, i");
        els.forEach(function (el) {
            if (el.children.length) return;
            var t = (el.textContent || "").trim();
            if (!t || !isEmojiChar(t)) return;
            var g = el.parentNode;
            if (!g || grids.indexOf(g) !== -1) return;
            if (gridLooksLikePicker(g)) grids.push(g);
        });
        return grids;
    }

    /* ── Поле ввода рядом с пикером ── */
    function findField(grid) {
        var scope = grid.closest("form, .bb-editor, .chat-panel, .chat-input-row, .comment-form") || document;
        return scope.querySelector("textarea") ||
               scope.querySelector('input[type="text"]') ||
               document.querySelector("textarea");
    }

    function insertToken(token, grid) {
        var field = findField(grid);
        if (!field) return;
        var start = field.selectionStart || 0;
        var end = field.selectionEnd || 0;
        field.value = field.value.slice(0, start) + token + field.value.slice(end);
        field.selectionStart = field.selectionEnd = start + token.length;
        field.focus();
        field.dispatchEvent(new Event("input", { bubbles: true }));
    }

    /* ── Пересборка сеток в GIF ── */
    function rebuildPickers() {
        if (!LIST || !LIST.length) return;
        findPickerGrids().forEach(function (grid) {
            grid.innerHTML = "";
            LIST.forEach(function (file) {
                var b = document.createElement("button");
                b.type = "button";
                b.className = "emoji-pick-btn";
                b.title = file.replace(/\.gif$/i, "");
                var img = document.createElement("img");
                img.src = "/static/emoji/" + file;
                img.alt = "";
                img.loading = "lazy";
                b.appendChild(img);
                b.addEventListener("click", function (e) {
                    e.preventDefault();
                    insertToken("[emoji:" + file + "]", grid);
                });
                grid.appendChild(b);
            });
        });
    }

    /* ── Наблюдатель + перехват кликов (ленивый пикер) ── */
    var timer = null;
    function schedule() {
        clearTimeout(timer);
        timer = setTimeout(function () {
            convertTokens(document.body);
            rebuildPickers();
        }, 60);
    }

    function init() {
        fetch("/static/emoji/list.json")
            .then(function (r) { return r.json(); })
            .then(function (list) {
                LIST = list || [];
                if (!LIST.length) return;
                convertTokens(document.body);
                rebuildPickers();

                // перехват клика: editor.js создаст пикер -> мы пересоберём
                document.addEventListener("click", function () {
                    setTimeout(rebuildPickers, 20);
                }, true);

                if ("MutationObserver" in window) {
                    new MutationObserver(schedule).observe(document.body, {
                        childList: true, subtree: true,
                    });
                }
                setInterval(function () {
                    convertTokens(document.body);
                    rebuildPickers();
                }, 2000);
            })
            .catch(function () {});
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
