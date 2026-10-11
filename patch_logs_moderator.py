"""
patch_logs_moderator.py

Даёт модераторам (moderator+) право просматривать логи.

Что делает:
1. В admin/routes.py заменяет @admin_required на @role_required('moderator')
   на маршрутах logs (список источников) и logs_browser (просмотр файлов).
2. Проверяет импорт role_required (добавляет, если отсутствует).
3. Создаёт резервную копию admin/routes.py.bak.

ВАЖНО: маршруты добавления/удаления источников остаются @owner_required
(только developer/owner) — скрипт их НЕ трогает.

Использование:
    python patch_logs_moderator.py
"""

import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ROUTES_PATH = PROJECT_ROOT / "admin" / "routes.py"
BACKUP_PATH = PROJECT_ROOT / "admin" / "routes.py.bak"


def main():
    if not ROUTES_PATH.exists():
        print(f"❌ Файл не найден: {ROUTES_PATH}")
        return

    content = ROUTES_PATH.read_text(encoding="utf-8")

    # ── Резервная копия ───────────────────────────────────────
    shutil.copy2(ROUTES_PATH, BACKUP_PATH)
    print(f"💾 Создан бэкап: {BACKUP_PATH.name}")

    # Проверяем, есть ли импорт role_required ДО изменений
    had_import = bool(re.search(r"\brole_required\b", content))

    # ── 1. Замена декораторов (только logs и logs_browser) ────
    content, n1 = re.subn(
        r"@admin_required(\s+def logs\()",
        r"@role_required('moderator')\1",
        content,
    )
    content, n2 = re.subn(
        r"@admin_required(\s+def logs_browser\()",
        r"@role_required('moderator')\1",
        content,
    )

    print(f"🔧 logs: заменено {n1}")
    print(f"🔧 logs_browser: заменено {n2}")

    # ── 2. Проверка импорта ───────────────────────────────────
    if not had_import:
        if "bp = Blueprint" in content:
            content = content.replace(
                "bp = Blueprint",
                "from auth.roles import role_required\n\nbp = Blueprint",
                1,
            )
            print("➕ Добавлен импорт: from auth.roles import role_required")
        else:
            content = "from auth.roles import role_required\n" + content
            print("➕ Добавлен импорт в начало файла")
    else:
        print("ℹ️  role_required уже присутствует в файле")

    # ── Сохранение ────────────────────────────────────────────
    ROUTES_PATH.write_text(content, encoding="utf-8")
    print(f"✅ Файл сохранён: {ROUTES_PATH.name}")

    # ── Проверка результата ───────────────────────────────────
    final = ROUTES_PATH.read_text(encoding="utf-8")
    ok1 = "@role_required('moderator')\ndef logs(" in final
    ok2 = "@role_required('moderator')\ndef logs_browser(" in final

    print()
    print("ПРОВЕРКА:")
    print(f"   logs → @role_required('moderator'):        {'✅' if ok1 else '❌'}")
    print(f"   logs_browser → @role_required('moderator'): {'✅' if ok2 else '❌'}")
    print()

    if ok1 and ok2:
        print("🎉 Готово! Перезапусти сайт, чтобы изменения вступили в силу.")
    else:
        print("⚠️  Что-то пошло не так. Восстанови из бэкапа:")
        print(f"   copy /Y \"{BACKUP_PATH}\" \"{ROUTES_PATH}\"")


if __name__ == "__main__":
    main()