"""
Базовые middleware/утилиты для бота.

Сейчас: простой обработчик необработанных исключений с логированием.
"""
from __future__ import annotations

import traceback
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.core.logging_cfg import logger


class ErrorsLoggingMiddleware(BaseMiddleware):
    """Логирует исключения в хэндлерах, не прерывая работу бота."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        try:
            return await handler(event, data)
        except Exception:  # noqa: BLE001
            logger.error("Исключение в обработчике:\n%s", traceback.format_exc())
            # Можно отправить пользователю сообщение об ошибке, если есть chat/message
            return None
