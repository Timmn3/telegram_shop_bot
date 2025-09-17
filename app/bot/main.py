from __future__ import annotations

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.core.config import settings
from app.core.logging_cfg import setup_logging, logger
from app.bot.handlers import register_all_handlers


async def main() -> None:
    """Главная асинхронная функция запуска бота."""
    setup_logging()
    logger.info("Запуск бота...")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    register_all_handlers(dp)

    logger.info("Бот запущен. Начинаю polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())