"""
assign_role.py

Быстрое назначение роли пользователю.
Измени STEAM_ID и ROLE_CODE ниже, затем просто запусти скрипт.
"""

from datetime import datetime
from pathlib import Path
from flask import Flask
from database.models import db, SiteUserRole, SiteRoleHistory

# ══════════════════════════════════════════════════════════════
# НАСТРОЙКИ — ИЗМЕНИ ЭТИ ЗНАЧЕНИЯ
# ══════════════════════════════════════════════════════════════

STEAM_ID = "76561198160108755"  # ← Твой Steam ID
ROLE_CODE = "developer"         # ← Роль: developer, owner, admin, moderator, player, vip, supporter

# ══════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_DB_PATH = PROJECT_ROOT / "local_db.sqlite3"

ROLE_NAMES = {
    'developer': 'Архитектор О-Сознания',
    'owner': 'Глава О-Сознания',
    'admin': 'Сотрудник О-Сознания',
    'moderator': 'Помощник О-Сознания',
    'player': 'Сталкер',
    'vip': 'VIP',
    'supporter': 'Поддержка проекта',
}


def assign_role(steam_id, role_code):
    """Назначает роль пользователю."""

    if role_code not in ROLE_NAMES:
        print(f"❌ Неизвестная роль: {role_code}")
        print(f"Доступные роли: {', '.join(ROLE_NAMES.keys())}")
        return

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{LOCAL_DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        # Удаляем старую роль сайта (если есть)
        deleted = SiteUserRole.query.filter_by(
            steam_id=steam_id
        ).filter(
            SiteUserRole.role_code.in_(['developer', 'owner', 'admin', 'moderator', 'player'])
        ).delete()

        if deleted:
            print(f"🗑️  Удалено старых ролей: {deleted}")

        # Назначаем новую
        new_role = SiteUserRole(
            steam_id=steam_id,
            role_code=role_code,
            assigned_by="system",
            assigned_at=datetime.utcnow(),
            expires_at=None,
        )
        db.session.add(new_role)

        # История
        history = SiteRoleHistory(
            steam_id=steam_id,
            role_code=role_code,
            action='assigned',
            changed_by="system",
            changed_at=datetime.utcnow(),
            comment="Назначена через скрипт assign_role.py",
        )
        db.session.add(history)

        db.session.commit()

    role_name = ROLE_NAMES.get(role_code, role_code)
    print(f"✅ Роль '{role_name}' назначена пользователю {steam_id}")


if __name__ == "__main__":
    print("=" * 60)
    print("НАЗНАЧЕНИЕ РОЛИ")
    print("=" * 60)
    print(f"Steam ID: {STEAM_ID}")
    print(f"Роль: {ROLE_CODE} ({ROLE_NAMES.get(ROLE_CODE, '?')})")
    print("=" * 60)
    print()

    assign_role(STEAM_ID, ROLE_CODE)