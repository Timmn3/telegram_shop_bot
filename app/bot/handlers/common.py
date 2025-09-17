"""
Общие хэндлеры:
- /start — приветствие
- /menu — открыть корневые категории каталога
- callback "cart:back_to_menu" — вернуться в каталог из корзины
- callback "noop" — заглушка для неактивных кнопок
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.core.logging_cfg import logger
from app.db.session import AsyncSessionFactory
from app.services.catalog_service import list_root_categories
from app.bot.keyboards.inline_catalog import build_categories_kb

common_router = Router(name="common")


@common_router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Приветствие и подсказки."""
    text = (
        "👋 Привет! Это магазин в Telegram.\n"
        "Посмотреть каталог: /menu\n"
        "Открыть корзину: /cart"
    )
    await message.answer(text)


@common_router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """Показать корневые категории каталога."""
    async with AsyncSessionFactory() as session:
        categories = await list_root_categories(session)
    kb = build_categories_kb(categories)
    await message.answer("🗂 Выберите категорию:", reply_markup=kb)
    logger.debug("Пользователь %s открыл меню каталога", message.from_user.id if message.from_user else None)


@common_router.callback_query(F.data == "cart:back_to_menu")
async def cb_back_to_menu(callback: CallbackQuery) -> None:
    """Вернуться в каталог (из пустой корзины и др.)."""
    async with AsyncSessionFactory() as session:
        categories = await list_root_categories(session)
    kb = build_categories_kb(categories)
    if callback.message:
        await callback.message.edit_text("🗂 Выберите категорию:", reply_markup=kb)
    await callback.answer()


@common_router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Ничего не делаем — тихо закрываем всплывашку."""
    await callback.answer()
