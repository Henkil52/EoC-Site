"""
check_env.py

Диагностика: какой .env загружается и какие FTP-переменные видны.
"""

import os

from env_config import load_env

env_path = load_env()

print("=" * 60)
print("ДИАГНОСТИКА .env")
print("=" * 60)
print(f"Загружен файл: {env_path}")
print()

print("FTP-переменные:")
for key in ['FTP_HOST', 'FTP_PORT', 'FTP_USERNAME', 'FTP_PASSWORD',
            'FTP_REMOTE_DIR', 'FTP_USE_SSL', 'ssl_verify_cert']:
    value = os.getenv(key)
    if value:
        # Маскируем пароль
        display = "***" if 'PASS' in key.upper() else value
        print(f"  ✅ {key} = {display}")
    else:
        print(f"  ❌ {key} = (пусто)")

print("=" * 60)