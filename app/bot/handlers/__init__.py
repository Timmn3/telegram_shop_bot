"""
Регистрация всех роутеров бота в Dispatcher.

Роутеры:
- common_router: команды /start, /menu
- catalog_router: каталог категорий и список товаров
- cart_router: корзина (добавление, просмотр, редактирование)
"""
from __future__ import annotations

from aiogram import Dispatcher

from .common import common_router
from .catalog import catalog_router
from .cart import cart_router


def register_all_handlers(dp: Dispatcher) -> None:
    """Регистрирует все роутеры приложения в диспетчере."""
    dp.include_router(common_router)
    dp.include_router(catalog_router)
    dp.include_router(cart_router)
