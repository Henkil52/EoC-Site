"""
patch_nav_logo.py

Добавляет логотип "Echo of Chernobyl | RP Project" в начало навбара.
Клик по логотипу ведёт на страницу новостей.

Использование:
    python patch_nav_logo.py
"""

import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
NAV_PATH = PROJECT_ROOT / "templates" / "includes" / "navbar.html"

LOGO_HTML = '''
    <a href="{{ url_for('news.index') }}" class="nav-logo" title="Перейти к новостям">
        <span class="nav-logo-icon">☢️</span>
        <span class="nav-logo-main">Echo of Chernobyl</span>
        <span class="nav-logo-sub">| RP Project</span>
    </a>
'''


def main():
    print("=" * 60)
    print("ПАТЧ: Логотип в навбаре")
    print("=" * 60)

    if not NAV_PATH.exists():
        print(f"❌ Файл не найден: {NAV_PATH}")
        return

    content = NAV_PATH.read_text(encoding="utf-8")

    if "nav-logo" in content:
        print("ℹ️  Логотип уже добавлен")
        return

    # Ищем открывающий тег навбара
    m = re.search(r'<nav\b[^>]*>', content)
    if not m:
        m = re.search(r'<header\b[^>]*>', content)
    if not m:
        print("❌ Не найден тег <nav> или <header>")
        return

    shutil.copy2(NAV_PATH, NAV_PATH.with_suffix(".html.bak"))
    content = content[:m.end()] + LOGO_HTML + content[m.end():]
    NAV_PATH.write_text(content, encoding="utf-8")

    print("✅ Логотип добавлен в навбар")
    print(f"💾 Бэкап: {NAV_PATH.name}.bak")
    print()
    print("🎉 Готово! Обнови страницу (Ctrl+F5).")


if __name__ == "__main__":
    main()