"""
fix_player_logs.py

Полная проверка и починка функции "Логи игрока":
1. Проверяет и чинит profile/routes.py (функция + передача в шаблон)
2. Проверяет и чинит шаблон профиля (скрытая вкладка)
3. Запускает сбор логов с FTP (sync_player_logs)
4. Показывает, у каких игроков есть логи

Использование:
    python fix_player_logs.py
"""

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

ROUTES_PATH = PROJECT_ROOT / "profile" / "routes.py"
TEMPLATE_PATH = PROJECT_ROOT / "profile" / "templates" / "profile" / "index.html"

# ── Код функции чтения логов ──────────────────────────────────
FUNC_CODE = '''def get_player_logs_data(steam_id, tail=100):
    """
    Читает локальные логи игрока (logs_players/<steam_id>/).
    Возвращает последние tail строк по каждому типу.
    """
    from sync.player_logs_sync import LOGS_DIR, LOG_TYPES, LOG_LABELS

    result = []
    user_dir = LOGS_DIR / steam_id

    if not user_dir.exists():
        return result

    for log_type in LOG_TYPES:
        path = user_dir / log_type

        if not path.exists():
            continue

        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except Exception:
            continue

        if not lines:
            continue

        result.append({
            'type': log_type,
            'label': LOG_LABELS.get(log_type, log_type),
            'lines': lines[-tail:],
            'total': len(lines),
            'truncated': len(lines) > tail,
        })

    return result


'''

# ── Блок вкладки для шаблона ──────────────────────────────────
TEMPLATE_BLOCK = '''            {# ── Логи игрока (только для администрации) ────── #}
            {% if is_moderator and player_logs %}
                <div class="player-logs">
                    <h3>🕵️ Логи игрока (администрация)</h3>

                    {% for log in player_logs %}
                        <details class="player-log-block">
                            <summary>
                                {{ log.label }}
                                <span class="log-count">({{ log.total }})</span>
                            </summary>

                            {% if log.truncated %}
                                <p class="hint">
                                    Показаны последние {{ log.lines|length }}
                                    из {{ log.total }} записей.
                                </p>
                            {% endif %}

                            <pre class="logs-pre">{% for line in log.lines %}{{ line }}
{% endfor %}</pre>
                        </details>
                    {% endfor %}
                </div>
            {% endif %}

'''


def check_and_fix_routes():
    print("🔧 [1/3] profile/routes.py")

    content = ROUTES_PATH.read_text(encoding="utf-8")
    changed = False

    if "def get_player_logs_data" not in content:
        idx = content.find("@bp.route")
        content = content[:idx] + FUNC_CODE + content[idx:]
        print("   ➕ добавлена функция get_player_logs_data")
        changed = True
    else:
        print("   ✅ функция на месте")

    if "player_logs = get_player_logs_data" not in content:
        old = "player_appeals = get_player_appeals(steam_id) if is_moderator else []"
        new = (
            "player_appeals = get_player_appeals(steam_id) if is_moderator else []\n"
            "    player_logs = get_player_logs_data(steam_id) if is_moderator else []"
        )
        n = content.count(old)
        content = content.replace(old, new)
        print(f"   ➕ добавлено присваивание player_logs ({n} маршрутов)")
        changed = True
    else:
        print("   ✅ присваивание на месте")

    if "player_logs=player_logs" not in content:
        old = "player_appeals=player_appeals,"
        new = "player_appeals=player_appeals,\n        player_logs=player_logs,"
        n = content.count(old)
        content = content.replace(old, new)
        print(f"   ➕ добавлен параметр в render_template ({n} мест)")
        changed = True
    else:
        print("   ✅ параметр передаётся")

    if changed:
        shutil.copy2(ROUTES_PATH, ROUTES_PATH.with_suffix(".py.bak"))
        ROUTES_PATH.write_text(content, encoding="utf-8")
        print("   💾 сохранено")


def check_and_fix_template():
    print("🔧 [2/3] Шаблон профиля")

    content = TEMPLATE_PATH.read_text(encoding="utf-8")

    if "player-logs" in content:
        print("   ✅ вкладка уже в шаблоне")
        return

    anchor = content.find('class="player-appeals"')
    if anchor == -1:
        anchor = content.find('class="player-stats"')
    if anchor == -1:
        print("   ❌ не найден якорь для вставки!")
        return

    section_end = content.find('</section>', anchor)
    if section_end == -1:
        print("   ❌ не найден конец секции!")
        return

    shutil.copy2(TEMPLATE_PATH, TEMPLATE_PATH.with_suffix(".html.bak"))
    content = content[:section_end] + TEMPLATE_BLOCK + content[section_end:]
    TEMPLATE_PATH.write_text(content, encoding="utf-8")
    print("   ➕ вкладка вставлена, 💾 сохранено")


def run_sync():
    print("🔧 [3/3] Сбор логов с FTP")

    try:
        from env_config import load_env
        load_env()
    except Exception as e:
        print(f"   ⚠️  не удалось загрузить .env: {e}")

    try:
        from sync.player_logs_sync import sync_player_logs, LOGS_DIR
        result = sync_player_logs()
        print(f"   ✅ собрано записей: {result['entries']}, игроков: {result['players']}")
    except Exception as e:
        print(f"   ❌ ошибка синхронизации: {e}")
        return

    # Показываем, у кого есть логи
    if LOGS_DIR.exists():
        print("\n📁 Логи по игрокам:")
        found = False
        for d in sorted(LOGS_DIR.iterdir()):
            if d.is_dir():
                files = [f.name for f in d.iterdir() if f.is_file()]
                if files:
                    found = True
                    print(f"   • {d.name}: {len(files)} файлов")
        if not found:
            print("   ⚠️  папок с логами нет — проверь FTP_REMOTE_DIR в .env")


def main():
    print("=" * 60)
    print("ПОЧИНКА: Логи игрока в профиле")
    print("=" * 60)

    check_and_fix_routes()
    print()
    check_and_fix_template()
    print()
    run_sync()

    print()
    print("=" * 60)
    print("✅ Готово! Теперь ПЕРЕЗАПУСТИ сайт и открой профиль")
    print("   игрока, у которого есть логи (например, свой — Henkil).")
    print("=" * 60)


if __name__ == "__main__":
    main()