"""
Сервис корзины.

Задачи:
- Получение/создание активной корзины.
- Добавление/изменение/удаление позиций.
- Подсчёт суммы корзины.

Вызывает методы CartRepo/ProductRepo. Все операции выполняются в транзакции.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Cart, CartItem
from app.db.repository import CartRepo


async def get_or_create_cart(session: AsyncSession, *, user_id: int) -> Cart:
    """Вернуть активную корзину пользователя (создать при отсутствии)."""
    async with session.begin():
        return await CartRepo.get_or_create_active_cart(session, user_id=user_id)


async def add_item(session: AsyncSession, *, user_id: int, product_id: int, quantity: int = 1) -> CartItem:
    """
    Добавить позицию в корзину (или увеличить количество).
    Бросает ValueError, если товара не существует или он неактивен.
    """
    if quantity <= 0:
        raise ValueError("Количество должно быть положительным")
    async with session.begin():
        return await CartRepo.add_item(session, user_id=user_id, product_id=product_id, quantity=quantity)


async def set_quantity(session: AsyncSession, *, user_id: int, product_id: int, quantity: int) -> Optional[CartItem]:
    """
    Установить точное количество позиции. Если quantity <= 0 — позиция удаляется.
    Возвращает обновлённый CartItem или None (если позиции не было/удалена).
    """
    async with session.begin():
        return await CartRepo.set_quantity(session, user_id=user_id, product_id=product_id, quantity=quantity)


async def remove_item(session: AsyncSession, *, user_id: int, product_id: int) -> None:
    """Удалить позицию из корзины (если была)."""
    async with session.begin():
        await CartRepo.remove_item(session, user_id=user_id, product_id=product_id)


async def clear_cart(session: AsyncSession, *, user_id: int) -> None:
    """Очистить корзину целиком."""
    async with session.begin():
        await CartRepo.clear(session, user_id=user_id)


async def list_items(session: AsyncSession, *, user_id: int) -> List[CartItem]:
    """Вернуть список позиций активной корзины пользователя."""
    # чтение допустимо и вне явной транзакции, но поддержим единообразие
    async with session.begin():
        return await CartRepo.get_items(session, user_id=user_id)


async def subtotal(session: AsyncSession, *, user_id: int) -> Decimal:
    """Подсчитать сумму корзины (Decimal)."""
    async with session.begin():
        return await CartRepo.subtotal(session, user_id=user_id)
