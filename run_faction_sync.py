"""
run_faction_sync.py

Ручной запуск синхронизации ролей в группировках.
"""

import sys
import logging
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync.faction_roles import sync_faction_roles

# Настройка цветного логирования
try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init()


    class ColoredFormatter(logging.Formatter):
        COLORS = {
            'DEBUG': Fore.CYAN,
            'INFO': Fore.GREEN,
            'WARNING': Fore.BLUE,
            'ERROR': Fore.RED,
        }
        RESET = Style.RESET_ALL

        def format(self, record):
            orig_levelname = record.levelname
            if orig_levelname in self.COLORS:
                record.levelname = self.COLORS[orig_levelname] + orig_levelname + self.RESET
            result = super().format(record)
            record.levelname = orig_levelname
            return result


    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter("%(asctime)s | %(levelname)s | %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])

except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

if __name__ == "__main__":
    sync_faction_roles()