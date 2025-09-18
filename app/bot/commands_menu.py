"""
Меню команд Telegram
"""
from __future__ import annotations

from aiogram import Router, Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from app.core.logging_cfg import logger
from app.core.config import settings

commands_menu_router = Router(name="commands_menu")

# Общий набор команд (видны всем)
COMMON_COMMANDS = [
    BotCommand(command="start", description="Начать"),
    BotCommand(command="menu", description="Каталог"),
    BotCommand(command="cart", description="Корзина"),
]

# Доп. команды только для админов (персонально в их чат)
ADMIN_EXTRA_COMMANDS = [
    BotCommand(command="admin", description="Админ-панель"),
    BotCommand(command="admin_add_product", description="Добавить товар (FSM)"),
]


async def set_common_commands(bot: Bot) -> None:
    """Установить общие команды для всех пользователей."""
    await bot.set_my_commands(COMMON_COMMANDS, scope=BotCommandScopeDefault())
    logger.info("Глобальные команды установлены")


async def set_admin_commands_for_chat(bot: Bot, chat_id: int) -> None:
    """
    Установить команды для КОНКРЕТНОГО чата админа.
    Безопасно вызывать только после того, как пользователь написал боту (/start).
    """
    try:
        await bot.set_my_commands(COMMON_COMMANDS + ADMIN_EXTRA_COMMANDS, scope=BotCommandScopeChat(chat_id=chat_id))
        logger.info("Команды для админа chat_id=%s установлены", chat_id)
    except Exception:
        # Ничего страшного, если чат ещё не существует или бот заблокирован.
        logger.exception("Не удалось установить команды для админа chat_id=%s", chat_id)


@commands_menu_router.startup()
async def on_startup_set_common(bot: Bot) -> None:
    """Хук запуска: выставляем только общие команды, без персональных."""
    await set_common_commands(bot)

    # Если очень хочется — можно мягко попробовать назначить для известных ADMIN_ID_LIST,
    # но не шумим в логах, если чатов ещё нет.
    for admin_id in (settings.ADMIN_ID_LIST or []):
        try:
            await bot.set_my_commands(COMMON_COMMANDS + ADMIN_EXTRA_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            # Тихо пропускаем — появится чат, назначим позже из /start
            pass
