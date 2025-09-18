from __future__ import annotations
"""
Сервис корзины.

Задачи:
- Получение/создание активной корзины.
- Добавление/изменение/удаление позиций.
- Подсчёт суммы корзины.

Вызывает методы CartRepo/ProductRepo. Все операции выполняются в транзакции.
"""

from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_cfg import logger
from app.db.models import Cart, CartItem
from app.db.repository import CartRepo


async def get_or_create_cart(session: AsyncSession, *, user_id: int) -> Cart:
    """Вернуть активную корзину пользователя (создать при отсутствии)."""
    logger.debug("cart_service.get_or_create_cart: user_id=%s", user_id)
    async with session.begin():
        cart = await CartRepo.get_or_create_active_cart(session, user_id=user_id)
    return cart


async def add_item(session: AsyncSession, *, user_id: int, product_id: int, quantity: int = 1) -> CartItem:
    """
    Добавить позицию в корзину (или увеличить количество).
    Бросает ValueError, если товара не существует или он неактивен.
    """
    if quantity <= 0:
        logger.warning("cart_service.add_item: non-positive qty user_id=%s product_id=%s qty=%s", user_id, product_id, quantity)
        raise ValueError("Количество должно быть положительным")

    logger.info("cart_service.add_item: user_id=%s product_id=%s +%s", user_id, product_id, quantity)
    async with session.begin():
        item = await CartRepo.add_item(session, user_id=user_id, product_id=product_id, quantity=quantity)
    return item


async def set_quantity(session: AsyncSession, *, user_id: int, product_id: int, quantity: int) -> Optional[CartItem]:
    """
    Установить точное количество позиции. Если quantity <= 0 — позиция удаляется.
    Возвращает обновлённый CartItem или None (если позиции не было/удалена).
    """
    logger.info("cart_service.set_quantity: user_id=%s product_id=%s -> qty=%s", user_id, product_id, quantity)
    async with session.begin():
        item = await CartRepo.set_quantity(session, user_id=user_id, product_id=product_id, quantity=quantity)
    return item


async def remove_item(session: AsyncSession, *, user_id: int, product_id: int) -> None:
    """Удалить позицию из корзины (если была)."""
    logger.info("cart_service.remove_item: user_id=%s product_id=%s", user_id, product_id)
    async with session.begin():
        await CartRepo.remove_item(session, user_id=user_id, product_id=product_id)


async def clear_cart(session: AsyncSession, *, user_id: int) -> None:
    """Очистить корзину целиком."""
    logger.info("cart_service.clear_cart: user_id=%s", user_id)
    async with session.begin():
        await CartRepo.clear(session, user_id=user_id)


async def list_items(session: AsyncSession, *, user_id: int) -> List[CartItem]:
    """Вернуть список позиций активной корзины пользователя."""
    logger.debug("cart_service.list_items: user_id=%s", user_id)
    # чтение допустимо и вне явной транзакции, но поддержим единообразие
    async with session.begin():
        items = await CartRepo.get_items(session, user_id=user_id)
    return items


async def subtotal(session: AsyncSession, *, user_id: int) -> Decimal:
    """Подсчитать сумму корзины (Decimal)."""
    logger.debug("cart_service.subtotal: user_id=%s", user_id)
    async with session.begin():
        total = await CartRepo.subtotal(session, user_id=user_id)
    return total
