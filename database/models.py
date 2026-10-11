"""
database/models.py

SQLAlchemy модели для локальной БД сайта.
"""

from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ──────────────────────────────────────────────
# Игровые таблицы (синхронизируются из MySQL)
# ──────────────────────────────────────────────


def moscow_now():
    """Текущее московское время (UTC+3, без перехода на летнее)."""
    from datetime import datetime, timedelta
    return datetime.utcnow() + timedelta(hours=3)


class Player(db.Model):
    """Основная таблица игроков."""
    __tablename__ = 'players'

    SteamID = db.Column(db.String(50), primary_key=True)
    Nickname = db.Column(db.String(50), nullable=True)
    RegistrationDate = db.Column(db.DateTime, nullable=False)
    LastLogonDate = db.Column(db.DateTime, nullable=False)

    stats = db.relationship('PlayerStats', backref='player', uselist=False)
    faction_membership = db.relationship('FactionMember', backref='player', uselist=False)
    achievements = db.relationship('PlayerAchievement', backref='player')
    pda_account = db.relationship('PdaAccount', backref='player', uselist=False)


class PlayerStats(db.Model):
    """Статистика игрока."""
    __tablename__ = 'player_stats'

    SteamID = db.Column(db.String(50), db.ForeignKey('players.SteamID'), primary_key=True)
    EmissionSurvived = db.Column(db.Integer, nullable=False, default=0)
    MutantsKills = db.Column(db.Integer, nullable=False, default=0)
    PlayerKills = db.Column(db.Integer, nullable=False, default=0)
    StashesFound = db.Column(db.Integer, nullable=False, default=0)
    ArtefactFound = db.Column(db.Integer, nullable=False, default=0)


class Faction(db.Model):
    """Фракции."""
    __tablename__ = 'factions'

    ID = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(50), nullable=False)
    SpawnPos = db.Column(db.String(50), nullable=True)
    MaxMembers = db.Column(db.Integer, nullable=False, default=10)
    Abilities = db.Column(db.Integer, nullable=False, default=0)
    Color = db.Column(db.BigInteger, nullable=False, default=0)
    Icon = db.Column(db.String(50), nullable=False)

    members = db.relationship('FactionMember', backref='faction')
    ranks = db.relationship('FactionRank', backref='faction')


class FactionRank(db.Model):
    """Ранги во фракциях."""
    __tablename__ = 'faction_ranks'

    RankID = db.Column(db.Integer, primary_key=True)
    FACTION_ID = db.Column(db.Integer, db.ForeignKey('factions.ID'), nullable=False)
    Name = db.Column(db.String(50), nullable=False)
    Permissions = db.Column(db.BigInteger, nullable=False, default=1023)


class FactionMember(db.Model):
    """Члены фракций."""
    __tablename__ = 'faction_members'

    FACTION_ID = db.Column(db.Integer, db.ForeignKey('factions.ID'), primary_key=True)
    RankID = db.Column(db.Integer, db.ForeignKey('faction_ranks.RankID'), primary_key=True)
    MEMBER_ID = db.Column(db.String(50), db.ForeignKey('players.SteamID'), primary_key=True)

    rank = db.relationship('FactionRank', backref='members')


class PlayerAchievement(db.Model):
    """Достижения игрока."""
    __tablename__ = 'player_achievements'

    SteamID = db.Column(db.String(50), db.ForeignKey('players.SteamID'), primary_key=True)
    AchievementID = db.Column(db.Integer, primary_key=True)
    IsAchieved = db.Column(db.Boolean, nullable=False, default=False)
    AchievedAt = db.Column(db.DateTime, nullable=True)
    Progress = db.Column(db.Text, nullable=False, default='{}')


class PdaAccount(db.Model):
    """Аккаунты PDA."""
    __tablename__ = 'pda_accounts'

    ID = db.Column(db.Integer, primary_key=True)
    Login = db.Column(db.String(50), nullable=False)
    SteamID = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    LastActivity = db.Column(db.DateTime, nullable=False)


# ──────────────────────────────────────────────
# Ролевая модель сайта
# ──────────────────────────────────────────────

class SiteRole(db.Model):
    """Справочник ролей сайта."""
    __tablename__ = 'site_roles'

    role_code = db.Column(db.String(50), primary_key=True)
    role_type = db.Column(db.String(20), nullable=False)  # 'site', 'faction', 'special'
    display_name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), nullable=True)
    color = db.Column(db.String(20), nullable=True)
    level = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<SiteRole {self.role_code} ({self.display_name})>"


class SiteUserRole(db.Model):
    """Роли пользователей сайта."""
    __tablename__ = 'site_user_roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    role_code = db.Column(db.String(50), db.ForeignKey('site_roles.role_code'), nullable=False)
    assigned_by = db.Column(db.String(50), nullable=True)  # Steam ID того, кто назначил
    assigned_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    expires_at = db.Column(db.DateTime, nullable=True)  # NULL = бессрочно

    role = db.relationship('SiteRole', backref='user_roles')

    def is_expired(self):
        """Проверяет, истекла ли роль."""
        if self.expires_at is None:
            return False
        return moscow_now() > self.expires_at

    def __repr__(self):
        return f"<SiteUserRole {self.steam_id}: {self.role_code}>"


class SiteFactionRole(db.Model):
    """Роли в группировках."""
    __tablename__ = 'site_faction_roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    faction_id = db.Column(db.Integer, db.ForeignKey('factions.ID'), nullable=False)
    steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    role_code = db.Column(db.String(50), nullable=False)  # faction_leader, faction_deputy, faction_member
    assigned_at = db.Column(db.DateTime, nullable=False, default=moscow_now)

    faction = db.relationship('Faction', backref='site_roles')

    def __repr__(self):
        return f"<SiteFactionRole {self.steam_id}: {self.role_code} in faction {self.faction_id}>"


class SiteWarning(db.Model):
    """Предупреждения пользователей."""
    __tablename__ = 'site_warnings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    given_by = db.Column(db.String(50), nullable=False)  # Steam ID того, кто дал предупреждение
    reason = db.Column(db.Text, nullable=False)
    given_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # NULL = бессрочно

    def is_expired(self):
        """Проверяет, истекло ли предупреждение."""
        if self.expires_at is None:
            return False
        return moscow_now() > self.expires_at

    def __repr__(self):
        return f"<SiteWarning {self.steam_id}: {self.reason[:50]}>"


class SiteRoleHistory(db.Model):
    """История изменения ролей."""
    __tablename__ = 'site_role_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    role_code = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(20), nullable=False)  # 'assigned', 'removed'
    changed_by = db.Column(db.String(50), nullable=False)  # Steam ID того, кто изменил
    changed_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    comment = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<SiteRoleHistory {self.steam_id}: {self.action} {self.role_code}>"

class SiteBan(db.Model):
    """Баны пользователей."""
    __tablename__ = 'site_bans'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    banned_by = db.Column(db.String(50), nullable=False)  # Steam ID того, кто забанил
    reason = db.Column(db.Text, nullable=False)
    banned_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    expires_at = db.Column(db.DateTime, nullable=True)  # NULL = перманентный бан
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def is_expired(self):
        """Проверяет, истек ли бан."""
        if self.expires_at is None:
            return False
        return moscow_now() > self.expires_at

    def __repr__(self):
        return f"<SiteBan {self.steam_id}: {self.reason[:50]}>"

# ──────────────────────────────────────────────
# Новости сайта
# ──────────────────────────────────────────────

class SiteNews(db.Model):
    """Новости сайта."""
    __tablename__ = 'site_news'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_html = db.Column(db.Text, nullable=True)   # ← добавь эту строку
    telegraph_url = db.Column(db.String(500), nullable=True)
    author_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    category = db.Column(db.String(50), nullable=False, default='other')
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    updated_at = db.Column(db.DateTime, nullable=True)

    comments = db.relationship('SiteNewsComment', backref='news', lazy='dynamic')

    def __repr__(self):
        return f"<SiteNews {self.id}: {self.title[:50]}>"


class SiteNewsComment(db.Model):
    """Комментарии к новостям."""
    __tablename__ = 'site_news_comments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    news_id = db.Column(db.Integer, db.ForeignKey('site_news.id'), nullable=False)
    author_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    content = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    updated_at = db.Column(db.DateTime, nullable=True)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<SiteNewsComment {self.id} (news {self.news_id})>"

# ──────────────────────────────────────────────
# Обращения (тикет-система)
# ──────────────────────────────────────────────

class SiteAppeal(db.Model):
    """Обращения игроков в администрацию."""
    __tablename__ = 'site_appeals'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    author_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    category = db.Column(db.String(50), nullable=False, default='other')
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    target_steam_id = db.Column(db.String(50), nullable=True)  # на кого жалоба
    status = db.Column(db.String(20), nullable=False, default='new')
    priority = db.Column(db.String(20), nullable=False, default='normal')
    assigned_to = db.Column(db.String(50), nullable=True)  # кто взял в работу
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    closed_by = db.Column(db.String(50), nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    messages = db.relationship('SiteAppealMessage', backref='appeal', lazy='dynamic')
    participants = db.relationship('SiteAppealParticipant', backref='appeal', lazy='dynamic')


class SiteAppealMessage(db.Model):
    """Сообщения внутри обращения (диалог)."""
    __tablename__ = 'site_appeal_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    appeal_id = db.Column(db.Integer, db.ForeignKey('site_appeals.id'), nullable=False)
    author_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_admin_reply = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)


class SiteAppealParticipant(db.Model):
    """Участники обращения (добавленные люди)."""
    __tablename__ = 'site_appeal_participants'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    appeal_id = db.Column(db.Integer, db.ForeignKey('site_appeals.id'), nullable=False)
    steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    added_by = db.Column(db.String(50), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=moscow_now)

# ──────────────────────────────────────────────
# Правила сайта
# ──────────────────────────────────────────────

class SiteRulesSection(db.Model):
    """Разделы правил."""
    __tablename__ = 'site_rules_sections'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=moscow_now)

    rules = db.relationship('SiteRule', backref='section', lazy='dynamic')


class SiteRule(db.Model):
    """Отдельные правила."""
    __tablename__ = 'site_rules'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    section_id = db.Column(db.Integer, db.ForeignKey('site_rules_sections.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=moscow_now)


class SiteRuleChange(db.Model):
    """Журнал изменений правил."""
    __tablename__ = 'site_rules_changes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    action = db.Column(db.String(20), nullable=False)       # create/update/delete/section_*
    target_type = db.Column(db.String(20), nullable=False)  # rule / section
    target_id = db.Column(db.Integer, nullable=True)
    section_title = db.Column(db.String(200), nullable=True)
    old_text = db.Column(db.Text, nullable=True)
    new_text = db.Column(db.Text, nullable=True)
    changed_by = db.Column(db.String(50), nullable=False)
    changed_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    change_number = db.Column(db.Integer,  nullable=True)  # Номер публикации (присваивается при публикации)
    news_id = db.Column(db.Integer, nullable=True)


class SiteCounter(db.Model):
    """Счётчики (номер изменения правил и т.д.)."""
    __tablename__ = 'site_counters'

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Integer, nullable=False, default=0)

# ──────────────────────────────────────────────
# Лор (история мира)
# ──────────────────────────────────────────────

class SiteLoreSection(db.Model):
    """Разделы лора."""
    __tablename__ = 'site_lore_sections'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=moscow_now)

    entries = db.relationship('SiteLore', backref='section', lazy='dynamic')


class SiteLore(db.Model):
    """Записи лора."""
    __tablename__ = 'site_lore'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    section_id = db.Column(db.Integer, db.ForeignKey('site_lore_sections.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=moscow_now)


class SiteLoreChange(db.Model):
    """Журнал изменений лора (без публикации новостей)."""
    __tablename__ = 'site_lore_changes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    action = db.Column(db.String(20), nullable=False)       # create/update/delete/section_*
    target_type = db.Column(db.String(20), nullable=False)  # lore / section
    target_id = db.Column(db.Integer, nullable=True)
    section_title = db.Column(db.String(200), nullable=True)
    entry_title = db.Column(db.String(200), nullable=True)
    old_text = db.Column(db.Text, nullable=True)
    new_text = db.Column(db.Text, nullable=True)
    changed_by = db.Column(db.String(50), nullable=False)
    changed_at = db.Column(db.DateTime, nullable=False, default=moscow_now)

# ──────────────────────────────────────────────
# Расширенная статистика (из player_database.json с FTP)
# ──────────────────────────────────────────────

class PlayerExtendedStats(db.Model):
    """Расширенная статистика игрока (синхронизируется с FTP)."""
    __tablename__ = 'player_extended_stats'

    SteamID = db.Column(db.String(50), db.ForeignKey('players.SteamID'), primary_key=True)
    FirstJoinDate = db.Column(db.DateTime, nullable=True)
    LastSeen = db.Column(db.DateTime, nullable=True)
    SessionCount = db.Column(db.Integer, nullable=False, default=0)
    TotalPlayTime = db.Column(db.Float, nullable=False, default=0)      # секунды
    Kills = db.Column(db.Integer, nullable=False, default=0)
    Deaths = db.Column(db.Integer, nullable=False, default=0)
    KDRatio = db.Column(db.Float, nullable=False, default=0)
    FavoriteWeapon = db.Column(db.String(100), nullable=True)
    FavoriteWeaponKills = db.Column(db.Integer, nullable=False, default=0)
    HeadshotKills = db.Column(db.Integer, nullable=False, default=0)
    HeadshotRatio = db.Column(db.Float, nullable=False, default=0)
    TotalDistanceTraveled = db.Column(db.Float, nullable=False, default=0)  # метры
    ItemsCrafted = db.Column(db.Integer, nullable=False, default=0)
    BuildingsConstructed = db.Column(db.Integer, nullable=False, default=0)
    TrapCount = db.Column(db.Integer, nullable=False, default=0)
    ZombieKills = db.Column(db.Integer, nullable=False, default=0)
    AnimalKills = db.Column(db.Integer, nullable=False, default=0)
    NamesHistory = db.Column(db.Text, nullable=True)   # JSON
    LastPosition = db.Column(db.Text, nullable=True)   # JSON

class PlayerWeaponStats(db.Model):
    """Статистика по каждому оружию игрока."""
    __tablename__ = 'player_weapon_stats'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    SteamID = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    WeaponName = db.Column(db.String(100), nullable=False)
    Kills = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint('SteamID', 'WeaponName', name='uq_player_weapon'),
    )


# ──────────────────────────────────────────────
# Источники логов (FTP-папки)
# ──────────────────────────────────────────────

class SiteLogSource(db.Model):
    """Зарегистрированные папки с логами на FTP."""
    __tablename__ = 'site_log_sources'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    ftp_path = db.Column(db.String(255), nullable=False)
    added_by = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<SiteLogSource {self.name}: {self.ftp_path}>"

# ──────────────────────────────────────────────
# Кастомные аватары игроков
# ──────────────────────────────────────────────

class SitePlayerAvatar(db.Model):
    """Кастомный аватар игрока (загруженный вручную)."""
    __tablename__ = 'site_player_avatars'

    steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=moscow_now)

    def __repr__(self):
        return f"<SitePlayerAvatar {self.steam_id}: {self.filename}>"


class SitePlayerBanner(db.Model):
    """Кастомный баннер игрока (загруженный вручную)."""
    __tablename__ = 'site_player_banners'

    steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=moscow_now)

    def __repr__(self):
        return f"<SitePlayerBanner {self.steam_id}: {self.filename}>"


class SitePrivacySettings(db.Model):
    """Настройки приватности игрока."""
    __tablename__ = 'site_privacy_settings'

    steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), primary_key=True)
    show_profile = db.Column(db.Boolean, nullable=False, default=True)
    show_online = db.Column(db.Boolean, nullable=False, default=False)
    allow_messages = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=moscow_now)

    def __repr__(self):
        return f"<SitePrivacySettings {self.steam_id}>"

# ──────────────────────────────────────────────
# Пользователи сайта (все, кто входил через Steam)
# ──────────────────────────────────────────────

class SiteUser(db.Model):
    """Учёт всех авторизаций на сайте через Steam."""
    __tablename__ = 'site_users'

    steam_id = db.Column(db.String(50), primary_key=True)
    nickname = db.Column(db.String(100), nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)
    profile_url = db.Column(db.String(500), nullable=True)
    first_site_login = db.Column(db.DateTime, nullable=False, default=moscow_now)
    last_site_login = db.Column(db.DateTime, nullable=False, default=moscow_now)
    login_count = db.Column(db.Integer, nullable=False, default=1)

    def __repr__(self):
        return f"<SiteUser {self.steam_id}: {self.nickname}>"


class SiteMessage(db.Model):
    """Личное сообщение между пользователями."""
    __tablename__ = 'site_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_steam_id = db.Column(db.String(50), nullable=False, index=True)
    recipient_steam_id = db.Column(db.String(50), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    is_read = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<SiteMessage {self.sender_steam_id} -> {self.recipient_steam_id}>"


# ═══════════════════════════════════════════════════════════════════
# СИСТЕМА ЗНАЧКОВ (BADGES)
# ═══════════════════════════════════════════════════════════════════

site_user_badges = db.Table(
    'site_user_badges',
    db.Column('user_steam_id', db.String(50), db.ForeignKey('players.SteamID'), primary_key=True),
    db.Column('badge_id', db.Integer, db.ForeignKey('site_badges.id'), primary_key=True),
    db.Column('awarded_at', db.DateTime, nullable=False, default=moscow_now),
    db.Column('awarded_by_steam_id', db.String(50), db.ForeignKey('players.SteamID'), nullable=True),
)


class SiteBadge(db.Model):
    """Значок (badge)."""
    __tablename__ = 'site_badges'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    created_by_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=True)
    
    users = db.relationship(
        'Player',
        secondary=site_user_badges,
        primaryjoin="SiteBadge.id == site_user_badges.c.badge_id",
        secondaryjoin="site_user_badges.c.user_steam_id == Player.SteamID",
        backref=db.backref('badges', lazy='dynamic'),
        lazy='dynamic'
    )
    
    def image_url(self):
        from flask import url_for
        return url_for('static', filename=f'badges/{self.image_filename}')


class SiteBadgeLog(db.Model):
    """Лог действий со значками."""
    __tablename__ = 'site_badge_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    action = db.Column(db.String(50), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('site_badges.id'), nullable=True)
    badge_name = db.Column(db.String(100), nullable=False)
    user_steam_id = db.Column(db.String(50), nullable=True)
    user_nickname = db.Column(db.String(50), nullable=True)
    actor_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    actor_nickname = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)


# ═══════════════════════════════════════════════════════════════════
# ОНЛАЙН-ЧАТ
# ═══════════════════════════════════════════════════════════════════

class SiteChatMessage(db.Model):
    """Сообщение общего чата."""
    __tablename__ = 'site_chat_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    author_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    text = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)


class SiteDialog(db.Model):
    """Личный диалог между двумя пользователями."""
    __tablename__ = 'site_dialogs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user1_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    user2_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)


class SitePrivateMessage(db.Model):
    """Сообщение в личном диалоге."""
    __tablename__ = 'site_private_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dialog_id = db.Column(db.Integer, db.ForeignKey('site_dialogs.id'), nullable=False)
    author_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    text = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    read_at = db.Column(db.DateTime, nullable=True)


class SiteFactionMessage(db.Model):
    """Сообщение в чате группировки."""
    __tablename__ = 'site_faction_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    faction_id = db.Column(db.Integer, db.ForeignKey('factions.ID'), nullable=False, index=True)
    author_steam_id = db.Column(db.String(50), db.ForeignKey('players.SteamID'), nullable=False)
    text = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)


class AchievementDef(db.Model):
    """Определение достижения: триггер, название, стикер."""
    __tablename__ = 'achievement_defs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kind = db.Column(db.String(10), nullable=False)  # location | item
    trigger = db.Column(db.String(100), nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    sticker = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)

    def __repr__(self):
        return f"<AchievementDef {self.kind}:{self.trigger}>"


class AchievementNotification(db.Model):
    """Уведомление о полученном достижении."""
    __tablename__ = 'achievement_notifications'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    steam_id = db.Column(db.String(50), nullable=False, index=True)
    def_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    sticker = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
    is_read = db.Column(db.Boolean, nullable=False, default=False)


from datetime import datetime


class CrosspostLog(db.Model):
    """Журнал кросспоста новостей (защита от дублей)."""
    __tablename__ = 'crosspost_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source = db.Column(db.String(20), nullable=False, index=True)  # telegram | discord
    external_id = db.Column(db.String(64), nullable=False, default="")
    news_id = db.Column(db.Integer, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=moscow_now)



class PlaytimeSnapshot(db.Model):
    """Дневной снапшот TotalPlayTime (для расчёта часов за 7 дней)."""
    __tablename__ = 'playtime_snapshots'
    __table_args__ = (db.UniqueConstraint('steam_id', 'snapshot_date'),)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    steam_id = db.Column(db.String(50), nullable=False, index=True)
    snapshot_date = db.Column(db.Date, nullable=False)
    total_playtime = db.Column(db.Float, nullable=False, default=0)
    recorded_at = db.Column(db.DateTime, nullable=False, default=moscow_now)
