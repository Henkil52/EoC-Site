"""
sync/scheduler.py

Планировщик для запуска синхронизации БД и публикации изменений правил.
Работает в фоновом потоке, не блокируя сайт.
"""

import logging

try:
    from colorama import Fore, Back, Style, init as colorama_init
    colorama_init()
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

from apscheduler.schedulers.background import BackgroundScheduler

from sync.db_sync import sync_database
from rules.service import publish_pending_changes


# ──────────────────────────────────────────────
# Цветной форматтер
# ──────────────────────────────────────────────

class ColoredFormatter(logging.Formatter):
    """Форматтер с цветами для консоли."""

    COLORS = {
        'DEBUG': Fore.CYAN if HAS_COLORAMA else '',
        'INFO': Fore.GREEN if HAS_COLORAMA else '',
        'WARNING': Fore.BLUE if HAS_COLORAMA else '',
        'ERROR': Fore.RED if HAS_COLORAMA else '',
        'CRITICAL': (Back.RED + Fore.WHITE) if HAS_COLORAMA else '',
    }
    RESET = Style.RESET_ALL if HAS_COLORAMA else ''

    def format(self, record):
        orig_levelname = record.levelname
        if orig_levelname in self.COLORS:
            record.levelname = self.COLORS[orig_levelname] + orig_levelname + self.RESET
        result = super().format(record)
        record.levelname = orig_levelname
        return result


# ──────────────────────────────────────────────
# Настройка логирования
# ──────────────────────────────────────────────

logger = logging.getLogger("db_scheduler")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        ColoredFormatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(stream_handler)


# ──────────────────────────────────────────────
# Планировщик
# ──────────────────────────────────────────────

scheduler = BackgroundScheduler()


def _check_publish_rules(app):
    """Обёртка для публикации изменений правил с обработкой ошибок."""
    try:
        with app.app_context():
            number = publish_pending_changes()
            if number:
                logger.info(f"📰 Опубликована новость: Изменение правил #{number}")
    except Exception as e:
        logger.error(f"Ошибка публикации изменений правил: {e}")


def start_sync_scheduler(interval_minutes=15, app=None):
    """Запускает планировщик синхронизации и публикаций."""

    # 1. Синхронизация игровой БД каждые 15 минут
    scheduler.add_job(
        func=sync_database,
        trigger="interval",
        minutes=interval_minutes,
        id="db_sync_job",
        name="Синхронизация игровой БД",
        replace_existing=True,
        max_instances=1,
    )

    # 2. Автозакрытие просроченных обращений
    try:
        from appeals.service import auto_close_stale_appeals

        scheduler.add_job(
            func=auto_close_stale_appeals,
            trigger="interval",
            minutes=interval_minutes,
            id="appeals_auto_close_job",
            name="Автозакрытие обращений",
            replace_existing=True,
            max_instances=1,
        )
    except ImportError:
        pass

    # 3. Публикация изменений правил (проверка каждую минуту)
    if app:
        scheduler.add_job(
            func=_check_publish_rules,
            args=[app],
            trigger="interval",
            minutes=1,
            id="rules_publish_job",
            name="Публикация изменений правил",
            replace_existing=True,
            max_instances=1,
        )

    if not scheduler.running:
        scheduler.start()
        logger.info(f"Планировщик запущен. Синхронизация: {interval_minutes} мин, публикация правил: 1 мин.")


def stop_sync_scheduler():
    """Останавливает планировщик."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Планировщик остановлен.")