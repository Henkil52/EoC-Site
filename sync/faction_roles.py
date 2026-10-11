"""
sync/faction_roles.py

Автоматическая синхронизация ролей в группировках на основе игровой БД.

Логика:
- Глава (faction_leader) — максимальный Permissions в группировке (1 на группировку)
- Заместитель (faction_deputy) — вторые по Permissions, максимум 2
  (второй только если в группировке > 7 человек)
- Участник (faction_member) — все остальные
"""

import logging
from datetime import datetime
from pathlib import Path
from flask import Flask

from database.models import (
    db,
    Faction,
    FactionRank,
    FactionMember,
    Player,
    SiteFactionRole,
)

logger = logging.getLogger("faction_roles_sync")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def sync_faction_roles():
    """
    Синхронизирует роли в группировках на основе данных из игровой БД.
    Вызывается автоматически после каждой синхронизации основной БД.
    """
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{PROJECT_ROOT / 'local_db.sqlite3'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        logger.info("=" * 60)
        logger.info("СИНХРОНИЗАЦИЯ РОЛЕЙ В ГРУППИРОВКАХ")
        logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        # Полностью очищаем таблицу site_faction_roles
        # и пересоздаём заново на основе актуальных данных
        deleted_count = SiteFactionRole.query.delete()
        logger.info(f"Удалено старых ролей: {deleted_count}")

        total_assigned = 0

        # Проходим по всем группировкам
        factions = Faction.query.all()

        for faction in factions:
            logger.info(f"Группировка: {faction.Name} (ID: {faction.ID})")

            # Получаем всех участников этой группировки с их рангами
            members = (
                db.session.query(FactionMember, FactionRank, Player)
                .join(FactionRank, FactionMember.RankID == FactionRank.RankID)
                .join(Player, FactionMember.MEMBER_ID == Player.SteamID)
                .filter(FactionMember.FACTION_ID == faction.ID)
                .order_by(FactionRank.Permissions.desc(), Player.Nickname.asc())
                .all()
            )

            members_count = len(members)
            logger.info(f"  Участников: {members_count} / {faction.MaxMembers}")

            if members_count == 0:
                logger.info(f"  ⚠️  Нет участников, пропускаю")
                continue

            # Группируем участников по уровню Permissions
            # (от большего к меньшему)
            permissions_levels = {}
            for member, rank, player in members:
                perm = rank.Permissions
                if perm not in permissions_levels:
                    permissions_levels[perm] = []
                permissions_levels[perm].append({
                    'member': member,
                    'rank': rank,
                    'player': player,
                })

            # Сортируем уровни по убыванию Permissions
            sorted_levels = sorted(permissions_levels.items(), reverse=True)

            # Назначаем роли
            assigned_leader = False
            assigned_deputies = 0

            for level_idx, (permissions, players_at_level) in enumerate(sorted_levels):
                for player_data in players_at_level:
                    player = player_data['player']
                    rank = player_data['rank']

                    # Определяем роль
                    if not assigned_leader:
                        # Первый с максимальными Permissions — глава
                        role_code = 'faction_leader'
                        assigned_leader = True
                    elif level_idx == 1 or (level_idx > 0 and assigned_deputies < (2 if members_count > 7 else 1)):
                        # Второй уровень Permissions — заместитель
                        # Максимум 1 заместитель, или 2 если > 7 человек
                        if assigned_deputies < (2 if members_count > 7 else 1):
                            role_code = 'faction_deputy'
                            assigned_deputies += 1
                        else:
                            role_code = 'faction_member'
                    else:
                        role_code = 'faction_member'

                    # Создаём запись
                    new_role = SiteFactionRole(
                        faction_id=faction.ID,
                        steam_id=player.SteamID,
                        role_code=role_code,
                        assigned_at=datetime.utcnow(),
                    )
                    db.session.add(new_role)
                    total_assigned += 1

                    logger.info(
                        f"    • {player.Nickname or player.SteamID:<20} | "
                        f"{rank.Name:<20} → {role_code}"
                    )

        db.session.commit()

        logger.info("")
        logger.info(f"✅ Всего назначено ролей: {total_assigned}")
        logger.info("=" * 60)

        return total_assigned


if __name__ == "__main__":
    # Настройка логирования для ручного запуска
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    sync_faction_roles()