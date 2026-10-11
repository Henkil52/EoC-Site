/*
 * user-picker.js
 * Выпадающий список пользователей с поиском по нику.
 * Активируется на <input data-user-picker="all|staff" [data-multi] [data-optional]>.
 */

(function () {
    'use strict';

    function getUsers(kind) {
        if (kind === 'staff') return window.STAFF_USERS || [];
        return window.SITE_USERS || [];
    }

    function initPicker(input) {
        var kind = input.getAttribute('data-user-picker');
        var multi = input.getAttribute('data-multi') === '1';
        var users = getUsers(kind);

        var hidden = input;
        hidden.type = 'hidden';
        hidden.removeAttribute('required');

        var wrap = document.createElement('div');
        wrap.className = 'user-picker';

        var box = document.createElement('div');
        box.className = 'user-picker-box';

        var list = document.createElement('ul');
        list.className = 'user-picker-list';

        var text = document.createElement('input');
        text.type = 'text';
        text.className = 'user-picker-input';
        text.placeholder = input.placeholder || 'Поиск по нику...';
        text.autocomplete = 'off';

        box.appendChild(text);
        wrap.appendChild(box);
        wrap.appendChild(list);
        hidden.parentNode.insertBefore(wrap, hidden);

        var selected = {};

        function fill(id) {
            for (var i = 0; i < users.length; i++) {
                if (users[i].id === id) return users[i].nick;
            }
            return id;
        }

        function syncHidden() {
            hidden.value = Object.keys(selected).join(',');
        }

        function renderChips() {
            box.querySelectorAll('.user-picker-chip').forEach(function (c) { c.remove(); });
            Object.keys(selected).forEach(function (id) {
                var chip = document.createElement('span');
                chip.className = 'user-picker-chip';
                chip.appendChild(document.createTextNode(selected[id]));
                var x = document.createElement('button');
                x.type = 'button';
                x.textContent = '\u00d7';
                x.addEventListener('click', function () {
                    delete selected[id];
                    syncHidden();
                    renderChips();
                });
                chip.appendChild(x);
                box.insertBefore(chip, text);
            });
        }

        function showList(q) {
            list.innerHTML = '';
            var query = (q || '').toLowerCase();
            var shown = 0;

            users.forEach(function (u) {
                if (multi && selected[u.id]) return;
                if (query &&
                    u.nick.toLowerCase().indexOf(query) === -1 &&
                    u.id.indexOf(query) === -1) return;
                if (shown >= 8) return;
                shown++;

                var li = document.createElement('li');
                li.textContent = u.nick;
                li.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    if (multi) {
                        selected[u.id] = u.nick;
                        syncHidden();
                        renderChips();
                        text.value = '';
                        list.classList.remove('open');
                    } else {
                        hidden.value = u.id;
                        text.value = u.nick;
                        list.classList.remove('open');
                    }
                });
                list.appendChild(li);
            });

            list.classList.toggle('open', shown > 0);
        }

        text.addEventListener('focus', function () { showList(text.value); });
        text.addEventListener('input', function () {
            if (!multi) hidden.value = '';
            showList(text.value);
        });
        text.addEventListener('blur', function () {
            setTimeout(function () { list.classList.remove('open'); }, 150);
        });

        // Инициализация из текущего значения
        if (hidden.value) {
            if (multi) {
                hidden.value.split(',').forEach(function (id) {
                    id = id.trim();
                    if (id) selected[id] = fill(id);
                });
                renderChips();
            } else {
                text.value = fill(hidden.value.trim());
            }
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('input[data-user-picker]').forEach(initPicker);
    });
})();
