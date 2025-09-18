"""
Общие хэндлеры
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.core.logging_cfg import logger
from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.db.models import User
from app.services.catalog_service import list_root_categories
from app.bot.keyboards.inline_catalog import build_categories_kb
from app.bot.commands_menu import set_admin_commands_for_chat  # <-- добавлено

common_router = Router(name="common")


@common_router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """
    Приветствие и однократное сохранение пользователя в БД.

    Логика:
    - Берём Telegram user_id и full_name из сообщения.
    - Если запись о пользователе отсутствует — создаём её.
    - Повторные /start не создают дубликаты (проверяем по PK id).
    - Если пользователь — админ (есть в ADMIN_ID_LIST), ставим ему персональные команды.
    """
    text = (
        "👋 Привет! Это магазин в Telegram.\n"
        "Посмотреть каталог: /menu\n"
        "Открыть корзину: /cart"
    )

    tg_id = message.from_user.id if message.from_user else None
    full_name = message.from_user.full_name if message.from_user else None

    if tg_id:
        # 1) Идемпотентно сохраняем пользователя
        async with AsyncSessionFactory() as session:
            exists = await session.get(User, tg_id)
            if not exists:
                session.add(User(id=tg_id, full_name=full_name))
                await session.commit()
                logger.info("Создан новый пользователь: id=%s, name=%r", tg_id, full_name)

        # 2) Если это админ — досыпаем персональные команды в ЭТОТ чат
        if tg_id in (settings.ADMIN_ID_LIST or []):
            await set_admin_commands_for_chat(message.bot, tg_id)

    else:
        logger.warning("Не удалось определить from_user.id для /start")

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
