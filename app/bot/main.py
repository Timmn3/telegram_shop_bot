"""
Точка входа Telegram-бота.

Инициализация:
- логирование
- Bot/Dispatcher
- FSM storage: Redis (если указан REDIS_URL) или in-memory
- регистрация роутеров
- запуск polling
"""
from __future__ import annotations

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

try:
    from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
    import redis.asyncio as redis  # type: ignore
except Exception:  # модуль может отсутствовать — не критично
    RedisStorage = None  # type: ignore

from app.core.config import settings
from app.core.logging_cfg import setup_logging, logger
from app.bot.handlers import register_all_handlers


def _make_storage():
    """Создаёт FSM storage: Redis или in-memory."""
    if RedisStorage and settings.REDIS_URL:
        client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        return RedisStorage(client=client, key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True))
    return MemoryStorage()


async def main() -> None:
    """Главная асинхронная функция запуска бота."""
    setup_logging()
    logger.info("Запуск бота...")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=_make_storage())

    register_all_handlers(dp)

    logger.info("Бот запущен. Начинаю polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
