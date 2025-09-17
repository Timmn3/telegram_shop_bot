"""
Общие хэндлеры:
- /start — приветствие, сохранение пользователя при первом входе (лениво, позже добавим)
- /menu — открыть корневые категории каталога
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.core.logging_cfg import logger
from app.db.session import AsyncSessionFactory
from app.services.catalog_service import list_root_categories
from app.bot.keyboards.inline_catalog import build_categories_kb

common_router = Router(name="common")


@common_router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """
    Команда /start:
    - Приветствие пользователя;
    - Предлагаем открыть меню каталога.
    """
    text = (
        "👋 Привет! Это магазин в Telegram.\n"
        "Посмотреть каталог: /menu"
    )
    await message.answer(text)


@common_router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """
    Команда /menu:
    - Показывает список корневых категорий с интерактивной клавиатурой.
    """
    async with AsyncSessionFactory() as session:
        categories = await list_root_categories(session)

    kb = build_categories_kb(categories)
    await message.answer("🗂 Выберите категорию:", reply_markup=kb)
    logger.debug("Пользователь %s открыл меню каталога", message.from_user.id if message.from_user else None)
