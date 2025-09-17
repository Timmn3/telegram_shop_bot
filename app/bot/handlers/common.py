"""
Общие хэндлеры:
- /start — приветствие + однократное сохранение пользователя в БД
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
from app.db.models import User  # <-- добавили
from app.services.catalog_service import list_root_categories
from app.bot.keyboards.inline_catalog import build_categories_kb

common_router = Router(name="common")


@common_router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """
    Приветствие и однократное сохранение пользователя в БД.

    Логика:
    - Берём Telegram user_id и full_name из сообщения.
    - Если запись о пользователе отсутствует — создаём её.
    - Повторные /start не создают дубликаты (проверяем по PK id).
    """
    text = (
        "👋 Привет! Это магазин в Telegram.\n"
        "Посмотреть каталог: /menu\n"
        "Открыть корзину: /cart"
    )

    tg_id = message.from_user.id if message.from_user else None
    full_name = message.from_user.full_name if message.from_user else None

    if tg_id:
        async with AsyncSessionFactory() as session:
            # idempotent: проверяем наличие пользователя по PK
            exists = await session.get(User, tg_id)
            if not exists:
                # создаём только один раз
                user = User(id=tg_id, full_name=full_name)
                session.add(user)
                await session.commit()
                logger.info("Создан новый пользователь: id=%s, name=%r", tg_id, full_name)
            else:
                logger.debug("Пользователь уже есть в БД: id=%s", tg_id)
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
