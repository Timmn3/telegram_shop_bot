"""
Регистрация всех роутеров бота в Dispatcher.
"""
from __future__ import annotations

from aiogram import Dispatcher

from .common import common_router
from .catalog import catalog_router
from .cart import cart_router
from .checkout import checkout_router


def register_all_handlers(dp: Dispatcher) -> None:
    dp.include_router(common_router)
    dp.include_router(catalog_router)
    dp.include_router(cart_router)
    dp.include_router(checkout_router)
