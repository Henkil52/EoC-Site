"""
fix_env_ubuntu.py

Универсальный поиск .env для Windows и Ubuntu:
1. env_config.py: добавляет пути /opt/env и /opt/env/.env
   (после Windows-путей — приоритет остаётся за Windows)
2. history_sync.py / news_sync.py: читают .env через env_config
   (раньше видели только папку проекта и родителя)
3. steam_utils.py: добавляет /opt/env в список кандидатов
4. Проверка: печатает, какие .env найдены прямо сейчас

Использование:
    python fix_env_ubuntu.py
"""

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKUP_DIR = Path(r"C:\Users\Администратор\Documents\bak")

UBUNTU_LINES = [
    'Path("/opt/env"),                               # Ubuntu: файл /opt/env',
    'Path("/opt/env/.env"),                          # Ubuntu: каталог /opt/env с .env',
]


def backup(path: Path):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, dst)
    print(f"      💾 бэкап: {dst.name}")


def patch_env_config():
    print("   📄 env_config.py:")
    p = PROJECT_ROOT / "env_config.py"
    content = p.read_text(encoding="utf-8")

    if "/opt/env" in content:
        print("      ℹ️  пути Ubuntu уже добавлены")
        return

    # Вставляем после последней Windows-строки списка
    anchor = None
    for a in (
        r'Path(r"C:\Users\Administrator\Documents\.env")',
        r'Path(r"C:\Users\Администратор\Documents\.env")',
        r'Path.home() / ".env"',
    ):
        if a in content:
            anchor = a
            break

    if anchor is None:
        print("      ⚠️  не нашёл точку вставки")
        return

    lines = content.splitlines()
    for i, line in enumerate(lines):
        if anchor in line:
            indent = line[: len(line) - len(line.lstrip())]
            for j, add in enumerate(UBUNTU_LINES, 1):
                lines.insert(i + j, indent + add)
            break

    backup(p)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("      ✅ добавлены /opt/env и /opt/env/.env (после Windows-путей)")


def patch_manual_readers():
    """history_sync.py и news_sync.py читали .env вручную только из 2 мест."""
    old_re = re.compile(
        r'([ \t]*)for p in \(PROJECT_ROOT / "\.env", PROJECT_ROOT\.parent / "\.env"\):'
    )
    for name in ("history_sync.py", "news_sync.py"):
        print(f"   📄 {name}:")
        p = PROJECT_ROOT / name
        if not p.exists():
            print("      ⚠️  файл не найден")
            continue
        content = p.read_text(encoding="utf-8")
        if "_fep()" in content:
            print("      ℹ️  уже использует env_config")
            continue

        def repl(m):
            ind = m.group(1)
            return (
                f"{ind}from env_config import find_env_paths as _fep\n"
                f"{ind}for p in (_fep() or [PROJECT_ROOT / '.env', PROJECT_ROOT.parent / '.env']):"
            )

        new_content, n = old_re.subn(repl, content)
        if n:
            backup(p)
            p.write_text(new_content, encoding="utf-8")
            print(f"      ✅ чтение .env через env_config ({n} мест)")
        else:
            print("      ⚠️  шаблон строки не найден — проверь вручную")


def patch_steam_utils():
    print("   📄 steam_utils.py:")
    p = PROJECT_ROOT / "steam_utils.py"
    content = p.read_text(encoding="utf-8")
    if "/opt/env" in content:
        print("      ℹ️  пути Ubuntu уже добавлены")
        return

    anchor = 'Path(__file__).resolve().parent.parent / ".env",'
    if anchor not in content:
        print("      ⚠️  не нашёл точку вставки")
        return

    lines = content.splitlines()
    for i, line in enumerate(lines):
        if anchor in line:
            indent = line[: len(line) - len(line.lstrip())]
            for j, add in enumerate(UBUNTU_LINES, 1):
                lines.insert(i + j, indent + add)
            break

    backup(p)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("      ✅ добавлены /opt/env и /opt/env/.env")


def verify():
    print("\n🔍 Проверка: какие .env видны прямо сейчас:")
    print("─" * 70)
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from env_config import find_env_paths
        paths = find_env_paths()
        if paths:
            for p in paths:
                print(f"   ✅ {p}")
        else:
            print("   ❌ ни одного .env не найдено")
        print("\n   Порядок поиска (первый существующий = главный):")
        print("   1. <проект>/.env")
        print("   2. ~/Documents/.env")
        print("   3. ~/.env")
        print("   4. C:\\Users\\Администратор\\Documents\\.env")
        print("   5. C:\\Users\\Administrator\\Documents\\.env")
        print("   6. /opt/env          ← Ubuntu")
        print("   7. /opt/env/.env     ← Ubuntu")
    except Exception as e:
        print(f"   ❌ ошибка импорта env_config: {e}")


def main():
    print("=" * 70)
    print("УНИВЕРСАЛЬНЫЙ .env: WINDOWS → UBUNTU (/opt/env)")
    print("=" * 70)

    patch_env_config()
    patch_manual_readers()
    patch_steam_utils()
    verify()

    print()
    print("=" * 70)
    print("🎉 Готово! Логика поиска:")
    print("   • На Windows: найдётся текущий .env (Documents) — всё как раньше")
    print("   • На Ubuntu: Windows-путей нет → возьмётся /opt/env")
    print()
    print("📦 НА UBUNTU ВЫПОЛНИ:")
    print("   sudo mkdir -p /opt/env_dir   # если хочешь держать как папку")
    print("   # вариант А: файл /opt/env")
    print("   sudo nano /opt/env           # вставь содержимое .env")
    print("   sudo chmod 600 /opt/env")
    print("   sudo chown ubuntu:ubuntu /opt/env")
    print()
    print("   Затем закоммить и запушить:")
    print("   git add . && git commit -m 'env: support /opt/env on Ubuntu' && git push")
    print("=" * 70)


if __name__ == "__main__":
    main()