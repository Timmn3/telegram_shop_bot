"""
Конфигурация логирования.

Возможности:
- Консольный логгер + файловый логгер с ротацией.
- Автосоздание папки logs/.
- Единая точка инициализации (вызвать setup_logging() при старте приложения).

"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings
from app.core.paths import LOG_DIR

# Глобальный логгер приложения
logger = logging.getLogger("tg_shop_bot")


def setup_logging() -> None:
    """Инициализирует логирование: консоль + файл с ротацией."""
    # Базовый уровень
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # Формат логов (включает время, уровень, модуль и сообщение)
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(module)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Консольный хэндлер
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)

    # Файловый хэндлер с ротацией
    log_file: Path = LOG_DIR / settings.LOG_FILE_NAME
    fh = RotatingFileHandler(
        filename=log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)

    # Чистим предыдущие хэндлеры (если повторно инициализируем)
    logger.handlers.clear()
    logger.addHandler(ch)
    logger.addHandler(fh)

    # Немного приглушим болтливые логгеры сторонних библиотек
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger.debug("Логирование инициализировано. Файл: %s", log_file)
