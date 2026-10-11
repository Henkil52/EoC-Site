"""
patch_bb_filter.py

Автоматически добавляет BB-фильтр |bb в main.py,
если его там нет. Создаёт бэкап.

Использование:
    python patch_bb_filter.py
"""

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MAIN_PATH = PROJECT_ROOT / "main.py"
BACKUP_PATH = PROJECT_ROOT / "main.py.bak"

FILTER_CODE = '''
    # ── BB-фильтр для форматированного текста ────────────────
    import re as _re
    from markupsafe import escape as _escape, Markup as _Markup

    @app.template_filter('bb')
    def bb_filter(text):
        """Безопасно преобразует BB-коды в HTML."""
        if not text:
            return ""

        s = str(_escape(text))  # защита от XSS

        # Блочные теги
        s = _re.sub(
            r'\\[quote\\](.*?)\\[/quote\\]',
            lambda m: '<blockquote class="bb-quote">' + m.group(1) + '</blockquote>',
            s, flags=_re.S | _re.I
        )
        s = _re.sub(
            r'\\[code\\](.*?)\\[/code\\]',
            lambda m: '<pre class="bb-code">' + m.group(1) + '</pre>',
            s, flags=_re.S | _re.I
        )

        # Списки
        def list_repl(m):
            items = _re.findall(r'\\[\\*\\]\\s*(.*?)(?=\\[\\*\\]|\\Z)', m.group(1), flags=_re.S)
            return '<ul class="bb-list">' + ''.join(f'<li>{i.strip()}</li>' for i in items) + '</ul>'

        s = _re.sub(r'\\[list\\](.*?)\\[/list\\]', list_repl, s, flags=_re.S | _re.I)

        # Строчные теги
        s = _re.sub(r'\\[b\\](.*?)\\[/b\\]', r'<strong>\\1</strong>', s, flags=_re.S | _re.I)
        s = _re.sub(r'\\[i\\](.*?)\\[/i\\]', r'<em>\\1</em>', s, flags=_re.S | _re.I)
        s = _re.sub(r'\\[u\\](.*?)\\[/u\\]', r'<u>\\1</u>', s, flags=_re.S | _re.I)
        s = _re.sub(r'\\[s\\](.*?)\\[/s\\]', r'<s>\\1</s>', s, flags=_re.S | _re.I)

        # Переносы строк
        s = s.replace('\\n', '<br>')

        return _Markup(s)

'''


def main():
    print("=" * 60)
    print("ПАТЧ: BB-фильтр в main.py")
    print("=" * 60)

    if not MAIN_PATH.exists():
        print(f"❌ Файл не найден: {MAIN_PATH}")
        return

    content = MAIN_PATH.read_text(encoding="utf-8")

    # Проверка: фильтр уже есть?
    if "@app.template_filter('bb')" in content:
        print("ℹ️  Фильтр |bb уже зарегистрирован в main.py")
        return

    # Ищем якорь: перед return app
    anchor = content.find("    return app")
    if anchor == -1:
        anchor = content.find("return app")
    if anchor == -1:
        print("❌ Не найден якорь 'return app' для вставки")
        return

    # Вставляем фильтр
    shutil.copy2(MAIN_PATH, BACKUP_PATH)
    content = content[:anchor] + FILTER_CODE + "\n" + content[anchor:]
    MAIN_PATH.write_text(content, encoding="utf-8")

    print("✅ Фильтр |bb добавлен в main.py")
    print(f"💾 Бэкап: {BACKUP_PATH.name}")
    print()
    print("=" * 60)
    print("🎉 Готово! Перезапусти сайт, чтобы фильтр заработал.")
    print("=" * 60)


if __name__ == "__main__":
    main()