"""
ftp_download.py

Скачивает все файлы из указанной FTP-папки в локальную папку ftp_download/,
сохраняя структуру, и объединяет всё текстовое содержимое в один файл
_ftp_dump.txt для анализа.

Показывает СЫРОЙ листинг директории для диагностики.
Поддерживает Unix и Windows форматы LIST.

Использование:
    python ftp_download.py
"""

import ftplib
import os
import ssl
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
DOWNLOAD_DIR = PROJECT_ROOT / "ftp_download"
DUMP_FILE = DOWNLOAD_DIR / "_ftp_dump.txt"

# Загружаем .env (все найденные файлы)
try:
    from env_config import find_env_paths
    env_paths = find_env_paths()
    if env_paths:
        for p in reversed(env_paths):
            load_dotenv(dotenv_path=p, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    load_dotenv(override=True)

# Цветной вывод
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
    GREEN = Fore.GREEN
    BLUE = Fore.BLUE
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    CYAN = Fore.CYAN
    MAGENTA = Fore.MAGENTA
    RESET = Style.RESET_ALL
    BOLD = Style.BRIGHT
except ImportError:
    GREEN = BLUE = YELLOW = RED = CYAN = MAGENTA = RESET = BOLD = ''


def get_ftp_config():
    """Читает настройки FTP из .env."""
    return {
        'host': os.getenv("FTP_HOST", "").strip(),
        'port': int(os.getenv("FTP_PORT", "21").strip() or "21"),
        'username': os.getenv("FTP_USERNAME", "").strip(),
        'password': os.getenv("FTP_PASSWORD", "").strip(),
        'remote_dir': os.getenv("FTP_REMOTE_DIR", "").strip(),
        'use_ssl': os.getenv("FTP_USE_SSL", "True").strip().lower() in ('true', '1', 'yes'),
        'verify_cert': os.getenv("ssl_verify_cert", "False").strip().lower() in ('true', '1', 'yes'),
    }


def connect_ftp(config):
    """Устанавливает FTP-соединение."""
    if not config['host']:
        print(f"{RED}❌ FTP_HOST не задан в .env{RESET}")
        return None

    print(f"{BLUE}🔌 Подключение к {config['host']}:{config['port']}...{RESET}")

    try:
        if config['use_ssl']:
            ctx = ssl.create_default_context()
            if not config['verify_cert']:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

            ftp = ftplib.FTP_TLS(context=ctx)
            ftp.connect(config['host'], config['port'], timeout=30)

            if config['username']:
                ftp.login(config['username'], config['password'])
            else:
                ftp.login()

            ftp.prot_p()
            print(f"{GREEN}✅ Подключено по FTPS (TLS){RESET}")
        else:
            ftp = ftplib.FTP()
            ftp.connect(config['host'], config['port'], timeout=30)

            if config['username']:
                ftp.login(config['username'], config['password'])
            else:
                ftp.login()

            print(f"{GREEN}✅ Подключено по FTP{RESET}")

        return ftp

    except Exception as e:
        print(f"{RED}❌ Ошибка подключения: {e}{RESET}")
        return None


def parse_list_line(line):
    """
    Разбирает строку листинга LIST.
    Поддерживает Unix и Windows (MSDOS) форматы.
    Возвращает dict {name, is_dir, size} или None.
    """
    line = line.rstrip()
    if not line:
        return None

    # ── Unix формат ──────────────────────────────────────────
    # drwxr-xr-x  2 user group  4096 Aug  7 10:15 folder
    # -rw-r--r--  1 user group  1234 Aug  7 10:15 file.txt
    if line[0] in 'dl-bcps':
        parts = line.split(None, 8)
        if len(parts) >= 9:
            size = 0
            if parts[4].isdigit():
                size = int(parts[4])
            return {
                'name': parts[8],
                'is_dir': parts[0].startswith('d'),
                'size': size,
            }
        return None

    # ── Windows (MSDOS) формат ───────────────────────────────
    # 08-07-26  10:15AM       <DIR>          folder
    # 08-07-26  10:15AM                 1234 file.txt
    parts = line.split(None, 3)
    if len(parts) >= 4:
        token3 = parts[2]
        name = parts[3]

        if token3.upper() == '<DIR>':
            return {'name': name, 'is_dir': True, 'size': 0}

        size = 0
        if token3.replace(',', '').isdigit():
            size = int(token3.replace(',', ''))

        return {'name': name, 'is_dir': False, 'size': size}

    return None


def list_files_recursive(ftp, path="", show_raw=False):
    """Рекурсивно получает список всех файлов и папок."""
    items = []

    try:
        lines = []
        ftp.retrlines(f"LIST {path}", lines.append)
    except Exception as e:
        print(f"{YELLOW}⚠️  Не удалось прочитать {path}: {e}{RESET}")
        return items

    # Показываем сырой листинг (для диагностики)
    if show_raw:
        print(f"\n{BLUE}📄 Сырой листинг '{path or '/'}':{RESET}")
        if lines:
            for line in lines:
                print(f"   | {line}")
        else:
            print(f"   | (пусто)")

    for line in lines:
        parsed = parse_list_line(line)
        if not parsed:
            continue

        name = parsed['name']

        # Пропускаем служебные записи
        if name in ('.', '..'):
            continue

        full_path = f"{path}/{name}" if path else name

        if parsed['is_dir']:
            items.append({
                'name': name,
                'path': full_path,
                'is_dir': True,
                'size': 0,
            })
            # Рекурсивно входим
            items.extend(list_files_recursive(ftp, full_path))
        else:
            items.append({
                'name': name,
                'path': full_path,
                'is_dir': False,
                'size': parsed['size'],
                'raw': line,
            })

    return items


def is_text_file(filename):
    """Определяет, является ли файл текстовым по расширению."""
    text_extensions = {
        '.txt', '.log', '.csv', '.json', '.xml', '.html', '.htm',
        '.md', '.ini', '.cfg', '.conf', '.yaml', '.yml', '.toml',
        '.py', '.js', '.css', '.sql', '.sh', '.bat', '.cmd',
        '.lua', '.properties', '.env', '',
    }
    return Path(filename).suffix.lower() in text_extensions


def read_text_content(ftp, remote_path):
    """Читает текстовый файл с FTP и возвращает содержимое."""
    lines = []

    try:
        def callback(line):
            lines.append(line)
        ftp.retrlines(f"RETR {remote_path}", callback)
        return '\n'.join(lines)
    except Exception as e:
        return f"[Ошибка чтения: {e}]"


def download_file(ftp, remote_path, local_path):
    """Скачивает файл с FTP."""
    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(local_path, 'wb') as f:
            ftp.retrbinary(f"RETR {remote_path}", f.write)
        return True
    except Exception as e:
        print(f"{RED}❌ Ошибка скачивания {remote_path}: {e}{RESET}")
        return False


def format_size(size_bytes):
    """Форматирует размер файла."""
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} МБ"
    else:
        return f"{size_bytes / (1024*1024*1024):.2f} ГБ"


def main():
    print(f"{BOLD}{GREEN}{'='*70}{RESET}")
    print(f"{BOLD}{GREEN}📥 СКАЧИВАНИЕ С FTP{RESET}")
    print(f"{BOLD}{GREEN}Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}{RESET}")
    print(f"{BOLD}{GREEN}{'='*70}{RESET}")

    config = get_ftp_config()

    print(f"\n{BLUE}📄 Найдены .env файлы:{RESET}")
    try:
        for p in find_env_paths():
            print(f"   • {p}")
    except NameError:
        pass

    print(f"\n{BLUE}📋 Параметры:{RESET}")
    print(f"   Host: {config['host']}")
    print(f"   Port: {config['port']}")
    print(f"   User: {config['username'] or '(anonymous)'}")
    print(f"   Remote dir: {config['remote_dir'] or '/'}")
    print(f"   SSL: {config['use_ssl']}")
    print(f"   Verify cert: {config['verify_cert']}")

    ftp = connect_ftp(config)
    if not ftp:
        return

    DOWNLOAD_DIR.mkdir(exist_ok=True)

    try:
        if config['remote_dir']:
            try:
                ftp.cwd(config['remote_dir'])
                print(f"{GREEN}✅ Перешли в {config['remote_dir']}{RESET}")
            except Exception as e:
                print(f"{YELLOW}⚠️  Не удалось перейти в {config['remote_dir']}: {e}{RESET}")

        current_dir = ftp.pwd()
        print(f"{BLUE}📁 Текущая директория: {current_dir}{RESET}")

        # Рекурсивно получаем список файлов (с сырым листингом)
        print(f"\n{BLUE}🔍 Сканирование файлов...{RESET}")
        items = list_files_recursive(ftp, show_raw=True)

        files = [item for item in items if not item['is_dir']]
        dirs = [item for item in items if item['is_dir']]

        total_size = sum(f['size'] for f in files)

        print(f"\n{BLUE}📊 Найдено:{RESET}")
        print(f"   Папок : {len(dirs)}")
        print(f"   Файлов: {len(files)}")
        print(f"   Размер: {format_size(total_size)}")

        if not files:
            print(f"\n{YELLOW}⚠️  Файлов не найдено{RESET}")
            ftp.quit()
            return

        # Скачиваем файлы и собираем дамп
        print(f"\n{MAGENTA}{'='*70}{RESET}")
        print(f"{BOLD}{MAGENTA}⬇️  СКАЧИВАНИЕ ФАЙЛОВ{RESET}")
        print(f"{MAGENTA}{'='*70}{RESET}")

        downloaded = 0
        text_files_dumped = 0

        with open(DUMP_FILE, 'w', encoding='utf-8') as dump:
            dump.write(f"FTP DUMP\n")
            dump.write(f"Host: {config['host']}:{config['port']}\n")
            dump.write(f"Remote dir: {current_dir}\n")
            dump.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            dump.write(f"Total files: {len(files)}\n")
            dump.write(f"Total size: {format_size(total_size)}\n")
            dump.write("=" * 70 + "\n\n")

            for i, item in enumerate(files, start=1):
                remote_path = item['path']
                local_path = DOWNLOAD_DIR / remote_path
                name = item['name']
                size = item['size']

                print(f"{CYAN}[{i}/{len(files)}]{RESET} {name} ({format_size(size)})")

                success = download_file(ftp, remote_path, local_path)
                if not success:
                    continue

                downloaded += 1

                if is_text_file(name) and size < 5 * 1024 * 1024:
                    content = read_text_content(ftp, remote_path)
                    dump.write(f"\n{'─'*70}\n")
                    dump.write(f"📄 FILE: {remote_path}\n")
                    dump.write(f"   SIZE: {format_size(size)}\n")
                    dump.write(f"   DOWNLOADED: {local_path}\n")
                    dump.write(f"{'─'*70}\n")
                    dump.write(content + "\n")
                    text_files_dumped += 1
                    print(f"   {GREEN}✓ Скачан + добавлен в дамп{RESET}")
                else:
                    dump.write(f"\n{'─'*70}\n")
                    dump.write(f"📦 BINARY/LARGE FILE: {remote_path}\n")
                    dump.write(f"   SIZE: {format_size(size)}\n")
                    dump.write(f"   DOWNLOADED: {local_path}\n")
                    dump.write(f"{'─'*70}\n")
                    print(f"   {GREEN}✓ Скачан (бинарный){RESET}")

        ftp.quit()

        print()
        print(f"{BOLD}{GREEN}{'='*70}{RESET}")
        print(f"{BOLD}{GREEN}📊 ИТОГОВАЯ СВОДКА{RESET}")
        print(f"{BOLD}{GREEN}{'='*70}{RESET}")
        print(f"  Скачано файлов        : {downloaded} / {len(files)}")
        print(f"  Текстовых в дамп      : {text_files_dumped}")
        print(f"  Папка с файлами       : {DOWNLOAD_DIR}")
        print(f"  Файл дампа            : {DUMP_FILE}")
        print(f"  Размер дампа          : {format_size(DUMP_FILE.stat().st_size)}")
        print(f"{BOLD}{GREEN}{'='*70}{RESET}")

    except Exception as e:
        print(f"{RED}❌ Ошибка: {e}{RESET}")
        import traceback
        traceback.print_exc()
        try:
            ftp.quit()
        except:
            pass


if __name__ == "__main__":
    main()