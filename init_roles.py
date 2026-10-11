"""
init_roles.py

Инициализация справочника ролей в локальной БД.
Запускать один раз при первом запуске проекта.
"""

from pathlib import Path
from flask import Flask
from database.models import db, SiteRole

PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_DB_PATH = PROJECT_ROOT / "local_db.sqlite3"

# Справочник ролей
ROLES = [
    # Роли сайта
    {
        "role_code": "developer",
        "role_type": "site",
        "display_name": "Архитектор О-Сознания",
        "icon": "⚙️",
        "color": "#8B5CF6",
        "level": 5,
        "description": "Разработчик сайта. Абсолютно все права.",
    },
    {
        "role_code": "owner",
        "role_type": "site",
        "display_name": "Глава О-Сознания",
        "icon": "👑",
        "color": "#FFD700",
        "level": 4,
        "description": "Владелец проекта. Полное управление сайтом.",
    },
    {
        "role_code": "admin",
        "role_type": "site",
        "display_name": "Сотрудник О-Сознания",
        "icon": "🛡️",
        "color": "#FF4444",
        "level": 3,
        "description": "Администратор сайта. Управление контентом и пользователями.",
    },
    {
        "role_code": "moderator",
        "role_type": "site",
        "display_name": "Помощник О-Сознания",
        "icon": "⚖️",
        "color": "#4488FF",
        "level": 2,
        "description": "Модератор. Модерация обращений и контента.",
    },
    {
        "role_code": "player",
        "role_type": "site",
        "display_name": "Сталкер",
        "icon": "🚶",
        "color": "#888888",
        "level": 1,
        "description": "Обычный игрок. Просмотр всех неограниченных разделов.",
    },

    # Роли группировок
    {
        "role_code": "faction_leader",
        "role_type": "faction",
        "display_name": "Глава группировки",
        "icon": "👑",
        "color": None,  # Цвет группировки
        "level": 3,
        "description": "Глава группировки. Один на группировку.",
    },
    {
        "role_code": "faction_deputy",
        "role_type": "faction",
        "display_name": "Заместитель",
        "icon": "🔸",
        "color": None,
        "level": 2,
        "description": "Заместитель главы группировки. Максимум 2.",
    },
    {
        "role_code": "faction_member",
        "role_type": "faction",
        "display_name": "Участник группировки",
        "icon": "🔹",
        "color": None,
        "level": 1,
        "description": "Участник группировки.",
    },

    # Специальные роли
    {
        "role_code": "vip",
        "role_type": "special",
        "display_name": "VIP",
        "icon": "💎",
        "color": "#FFD700",
        "level": 0,
        "description": "VIP игрок. Специальные привилегии.",
    },
    {
        "role_code": "supporter",
        "role_type": "special",
        "display_name": "Поддержка проекта",
        "icon": "🤝",
        "color": "#44BB44",
        "level": 0,
        "description": "Поддержка проекта. Благодарность за вклад.",
    },
]


def init_roles():
    """Создаёт справочник ролей в локальной БД."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{LOCAL_DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        # Создаём таблицы (если их нет)
        db.create_all()

        # Добавляем роли
        for role_data in ROLES:
            existing = SiteRole.query.filter_by(role_code=role_data["role_code"]).first()
            if not existing:
                role = SiteRole(**role_data)
                db.session.add(role)
                print(f"✅ Добавлена роль: {role_data['display_name']}")
            else:
                print(f"ℹ️  Роль уже существует: {role_data['display_name']}")

        db.session.commit()

    print("\n✅ Инициализация ролей завершена!")


if __name__ == "__main__":
    init_roles()