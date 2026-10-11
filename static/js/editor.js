/*
 * editor.js
 * Лёгкий BB-редактор: панель форматирования + смайлики.
 * Автоматически подключается ко всем <textarea class="rich-editor">.
 */

(function () {
    'use strict';

    let EMOJI_LIST = null;
    const EMOJI_WAITERS = [];

    function loadEmojiList(cb) {
        if (EMOJI_LIST) { cb(EMOJI_LIST); return; }
        EMOJI_WAITERS.push(cb);
        if (EMOJI_WAITERS.length > 1) return;
        fetch('/static/emoji/list.json')
            .then(function (r) { return r.json(); })
            .then(function (list) {
                EMOJI_LIST = list || [];
                EMOJI_WAITERS.splice(0).forEach(function (f) { f(EMOJI_LIST); });
            })
            .catch(function () {
                EMOJI_LIST = [];
                EMOJI_WAITERS.splice(0).forEach(function (f) { f(EMOJI_LIST); });
            });
    }

    const CMDS = [
        { icon: '<b>Ж</b>',  title: 'Жирный',        before: '[b]',     after: '[/b]' },
        { icon: '<i>К</i>',  title: 'Курсив',        before: '[i]',     after: '[/i]' },
        { icon: '<u>П</u>',  title: 'Подчёркнутый',  before: '[u]',     after: '[/u]' },
        { icon: '<s>З</s>',  title: 'Зачёркнутый',   before: '[s]',     after: '[/s]' },
        { icon: '❝',        title: 'Цитата',        before: '[quote]', after: '[/quote]' },
        { icon: '&lt;/&gt;', title: 'Код',      before: '[code]',  after: '[/code]' },
        { icon: '• Список', title: 'Список',        before: '[list]\n[*] ', after: '\n[/list]' },
    ];

    function insertAtCursor(ta, text) {
        const start = ta.selectionStart || 0;
        const end = ta.selectionEnd || 0;
        ta.value = ta.value.slice(0, start) + text + ta.value.slice(end);
        ta.focus();
        ta.selectionStart = ta.selectionEnd = start + text.length;
        ta.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function wrapSelection(ta, before, after) {
        const start = ta.selectionStart || 0;
        const end = ta.selectionEnd || 0;
        const sel = ta.value.slice(start, end) || 'текст';
        ta.value = ta.value.slice(0, start) + before + sel + after + ta.value.slice(end);
        ta.focus();
        ta.selectionStart = start + before.length;
        ta.selectionEnd = start + before.length + sel.length;
        ta.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function buildPicker(ta) {
        const picker = document.createElement('div');
        picker.className = 'emoji-picker';

        loadEmojiList(function (list) {
            list.forEach(function (file) {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'emoji-pick-btn';
                btn.title = file.replace(/\.gif$/i, '');
                const img = document.createElement('img');
                img.src = '/static/emoji/' + file;
                img.alt = '';
                img.loading = 'lazy';
                btn.appendChild(img);
                btn.addEventListener('click', function () {
                    insertAtCursor(ta, '[emoji:' + file + ']');
                    picker.classList.remove('open');
                });
                picker.appendChild(btn);
            });
            if (!list.length) {
                const empty = document.createElement('div');
                empty.style.padding = '10px';
                empty.style.color = 'var(--muted)';
                empty.textContent = 'Смайлы не найдены в static/emoji/';
                picker.appendChild(empty);
            }
        });

        return picker;
    }

    function initEditor(ta) {
        const bar = document.createElement('div');
        bar.className = 'editor-toolbar';

        CMDS.forEach(function (cmd) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.title = cmd.title;
            btn.innerHTML = cmd.icon;
            btn.addEventListener('click', function () {
                wrapSelection(ta, cmd.before, cmd.after);
            });
            bar.appendChild(btn);
        });

        // Кнопка смайликов
        const emojiBtn = document.createElement('button');
        emojiBtn.type = 'button';
        emojiBtn.title = 'Смайлики';
        emojiBtn.textContent = '😊';
        const picker = buildPicker(ta);
        emojiBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            picker.classList.toggle('open');
        });
        bar.appendChild(emojiBtn);
        bar.appendChild(picker);

        ta.parentNode.insertBefore(bar, ta);
        ta.classList.add('editor-area');
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('textarea.rich-editor').forEach(initEditor);

        // Закрывать пикер при клике вне
        document.addEventListener('click', function (e) {
            document.querySelectorAll('.emoji-picker.open').forEach(function (p) {
                if (!p.contains(e.target)) p.classList.remove('open');
            });
        });
    });
})();