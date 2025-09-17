"""
Пути проекта и общие константы.

"""
from __future__ import annotations

from pathlib import Path

# Корень проекта определяется как два уровня выше текущего файла:
BASE_DIR: Path = Path(__file__).resolve().parents[2]

# Папка для логов
LOG_DIR: Path = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
