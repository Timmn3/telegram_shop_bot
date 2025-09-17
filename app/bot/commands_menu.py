"""
Меню команд Telegram

Логика:
- На событии старта (startup) выставляем команды:
  * Общие (для всех): /start, /menu, /cart
  * Персональные для админов (из settings.ADMIN_ID_LIST): + /admin, /admin_add_product

Файл подключается через include_router(...) в общем регистраторе роутеров.
"""
from __future__ import annotations

from typing import Iterable

from aiogram import Router, Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from app.core.config import settings
from app.core.logging_cfg import logger

commands_menu_router = Router(name="commands_menu")


async def _setup_bot_commands(bot: Bot, *, admin_ids: Iterable[int]) -> None:
    """Установить меню команд: общие + персонально для админов."""
    # Общие команды (видны всем пользователям бота)
    common = [
        BotCommand(command="start", description="Начать и сохранить профиль"),
        BotCommand(command="menu", description="Каталог"),
        BotCommand(command="cart", description="Корзина"),
    ]
    await bot.set_my_commands(common, scope=BotCommandScopeDefault())

    # Персональные команды админам (добавляем поверх общих)
    admin_extra = [
        BotCommand(command="admin", description="Админ-панель"),
        BotCommand(command="admin_add_product", description="Добавить товар (FSM)"),
    ]
    for admin_id in admin_ids or []:
        try:
            await bot.set_my_commands(common + admin_extra, scope=BotCommandScopeChat(chat_id=admin_id))
            logger.info("Команды для админа %s установлены", admin_id)
        except Exception:
            logger.exception("Не удалось установить команды для админа %s", admin_id)


@commands_menu_router.startup()  # вызовется автоматически при запуске dp
async def on_startup_set_commands(bot: Bot) -> None:
    """Хук старта: выставляем команды при запуске приложения."""
    await _setup_bot_commands(bot, admin_ids=settings.ADMIN_ID_LIST)