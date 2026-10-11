"""
check_roles.py

Проверка ролей в локальной БД.
"""

from pathlib import Path
from flask import Flask
from database.models import db, SiteUserRole, SiteRole, SiteRoleHistory

PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_DB_PATH = PROJECT_ROOT / "local_db.sqlite3"


def check_roles():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{LOCAL_DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        print("=" * 60)
        print("ПРОВЕРКА РОЛЕЙ В ЛОКАЛЬНОЙ БД")
        print("=" * 60)
        print()

        # Справочник ролей
        print("📋 Справочник ролей (site_roles):")
        roles = SiteRole.query.all()
        if roles:
            for role in roles:
                print(f"  • {role.icon} {role.display_name} ({role.role_code})")
        else:
            print("  ⚠️  Справочник пуст! Запустите init_roles.py")

        print()

        # Назначенные роли
        print("👥 Назначенные роли пользователей (site_user_roles):")
        user_roles = SiteUserRole.query.all()
        if user_roles:
            for ur in user_roles:
                role = SiteRole.query.filter_by(role_code=ur.role_code).first()
                role_name = role.display_name if role else ur.role_code
                expires = ur.expires_at.strftime("%d.%m.%Y") if ur.expires_at else "бессрочно"
                print(f"  • {ur.steam_id}: {role_name} (истекает: {expires})")
        else:
            print("  ⚠️  Ролей не назначено! Запустите assign_role.py")

        print()

        # История изменений
        print("📜 История изменений ролей (site_role_history):")
        history = SiteRoleHistory.query.order_by(SiteRoleHistory.changed_at.desc()).all()
        if history:
            for h in history:
                print(f"  • {h.steam_id}: {h.action} {h.role_code} ({h.changed_at.strftime('%d.%m.%Y %H:%M')})")
        else:
            print("  ⚠️  История пуста")

        print()
        print("=" * 60)


if __name__ == "__main__":
    check_roles()