"""
show_navbar.py

Выводит текущее содержимое navbar.html для диагностики.
"""

from pathlib import Path

p = Path(__file__).resolve().parent / "templates" / "includes" / "navbar.html"

if p.exists():
    print("=" * 60)
    print(f"ФАЙЛ: {p}")
    print("=" * 60)
    print(p.read_text(encoding="utf-8"))
    print("=" * 60)
else:
    print(f"❌ Файл не найден: {p}")