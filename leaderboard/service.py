"""
leaderboard/service.py

Логика таблицы лидеров и автоматических бейджей.
Бейджи выдаются динамически: лидер категории получает бейдж,
при смене лидера бейдж автоматически переходит к новому.
"""

from sqlalchemy import desc, func

from database.models import db, Player, PlayerStats, PlayerExtendedStats


# Категории лидеров
LEADER_CATEGORIES = {
    'hunter': {
        'title': 'Лучший охотник',
        'icon': '🏆',
        'model': 'PlayerStats',
        'field': 'MutantsKills',
        'description': 'Убито мутантов',
        'color': '#44BB44',
    },
    'fighter': {
        'title': 'Лучший боец',
        'icon': '🔫',
        'model': 'PlayerStats',
        'field': 'PlayerKills',
        'description': 'Убито игроков',
        'color': '#FF4444',
    },
    'stalker': {
        'title': 'Лучший сталкер',
        'icon': '🔍',
        'model': 'PlayerStats',
        'field': 'StashesFound',
        'description': 'Найдено тайников',
        'color': '#4488FF',
    },
    'dedicated': {
        'title': 'Самый преданный',
        'icon': '⏱️',
        'model': 'PlayerExtendedStats',
        'field': 'TotalPlayTime',
        'description': 'Время в игре',
        'color': '#FFA500',
        'format': 'hours',
    },
    'sniper': {
        'title': 'Лучший снайпер',
        'icon': '🎯',
        'model': 'PlayerExtendedStats',
        'field': 'HeadshotRatio',
        'description': 'Процент хедшотов',
        'color': '#8B5CF6',
        'format': 'percent',
        'min_field': 'HeadshotKills',
        'min_value': 3,
    },
    'traveler': {
        'title': 'Лучший путешественник',
        'icon': '🏃',
        'model': 'PlayerExtendedStats',
        'field': 'TotalDistanceTraveled',
        'description': 'Пройдено расстояния',
        'color': '#00BCD4',
        'format': 'km',
    },
}


def _get_model(model_name):
    """Возвращает модель по имени."""
    return {
        'PlayerStats': PlayerStats,
        'PlayerExtendedStats': PlayerExtendedStats,
    }[model_name]


def format_value(code, value):
    """Форматирует значение лидера для отображения."""
    cat = LEADER_CATEGORIES.get(code, {})
    fmt = cat.get('format')

    if fmt == 'hours':
        return f"{value / 3600:.1f} ч"
    if fmt == 'km':
        return f"{value / 1000:.1f} км"
    if fmt == 'percent':
        return f"{value * 100:.0f}%"

    return str(int(value))


def get_leaderboards():
    """Возвращает отсортированные списки игроков по каждой категории."""
    result = {}

    for code, cat in LEADER_CATEGORIES.items():
        Model = _get_model(cat['model'])

        query = (
            db.session.query(Player, Model)
            .join(Model, Player.SteamID == Model.SteamID)
            .filter(getattr(Model, cat['field']) > 0)
        )

        # Минимальный порог (например, для снайпера — минимум 3 хедшота)
        if cat.get('min_field'):
            query = query.filter(
                getattr(Model, cat['min_field']) >= cat['min_value']
            )

        rows = query.order_by(desc(getattr(Model, cat['field']))).all()

        leaders = [
            {
                'player': p,
                'value': getattr(m, cat['field']),
                'display': format_value(code, getattr(m, cat['field'])),
            }
            for p, m in rows
        ]

        result[code] = {
            'category': cat,
            'leaders': leaders,
        }

    return result


def get_player_leader_badges(steam_id):
    """
    Возвращает лидерские бейджи игрока.
    Игрок получает бейдж, если он лидер (максимум) в категории.
    """
    if not steam_id:
        return []

    badges = []

    for code, cat in LEADER_CATEGORIES.items():
        Model = _get_model(cat['model'])

        stat = Model.query.filter_by(SteamID=steam_id).first()
        if not stat:
            continue

        value = getattr(stat, cat['field'])
        if value <= 0:
            continue

        # Минимальный порог
        if cat.get('min_field') and getattr(stat, cat['min_field']) < cat['min_value']:
            continue

        # Максимум среди подходящих
        max_query = (
            db.session.query(func.max(getattr(Model, cat['field'])))
            .filter(getattr(Model, cat['field']) > 0)
        )
        if cat.get('min_field'):
            max_query = max_query.filter(
                getattr(Model, cat['min_field']) >= cat['min_value']
            )

        max_value = max_query.scalar() or 0

        if max_value > 0 and value == max_value:
            badges.append({
                'code': code,
                'title': cat['title'],
                'icon': cat['icon'],
                'color': cat['color'],
                'value': format_value(code, max_value),
                'description': cat['description'],
            })

    return badges