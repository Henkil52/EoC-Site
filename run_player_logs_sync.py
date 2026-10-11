"""
run_player_logs_sync.py

Ручной запуск сбора логов игроков с FTP.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from env_config import load_env
load_env()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

from sync.player_logs_sync import sync_player_logs

if __name__ == "__main__":
    print("Запуск сбора логов игроков...")
    result = sync_player_logs()
    print(f"Новых записей: {result['entries']}")
    print(f"Игроков затронуто: {result['players']}")