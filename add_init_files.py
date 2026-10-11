from pathlib import Path


# Если хочешь сначала только посмотреть, что будет создано,
# поставь DRY_RUN = True.
DRY_RUN = False


EXCLUDE_DIRS = {
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "static",
    "templates",
    "instance",
    ".pytest_cache",
}


root = Path(__file__).resolve().parent


def is_excluded(path: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part in EXCLUDE_DIRS for part in relative_parts)


created = []
already_exists = []


for directory in root.rglob("*"):
    if not directory.is_dir():
        continue

    if directory == root:
        continue

    if is_excluded(directory):
        continue

    # Создаём __init__.py только в тех папках, где есть Python-файлы.
    # Например: news/routes.py, auth/routes.py и т.д.
    has_python_files = any(directory.glob("*.py"))

    if not has_python_files:
        continue

    init_file = directory / "__init__.py"

    if init_file.exists():
        already_exists.append(init_file)
        continue

    if DRY_RUN:
        print(f"[DRY RUN] Будет создан: {init_file}")
    else:
        init_file.touch(exist_ok=True)
        created.append(init_file)


print("\nСоздано файлов __init__.py:")
if created:
    for path in created:
        print(" ", path)
else:
    print("  Не было создано ни одного файла.")


print("\nУже существовало:")
if already_exists:
    for path in already_exists:
        print(" ", path)
else:
    print("  Не найдено существующих файлов __init__.py.")