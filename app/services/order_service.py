from __future__ import annotations
"""
Сервис заказов.

Задачи:
- Создать заказ из корзины (с генерацией номера).
- Получить заказ / список заказов.
- Изменение статуса заказа (для админ-панели).

Важно:
- create_order_from_cart выполняется в одной транзакции — ACID.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_cfg import logger
from app.db.models import Order, OrderStatus
from app.db.repository import OrderRepo


async def create_order_from_cart(
    session: AsyncSession,
    *,
    user_id: int,
    contact_name: str,
    contact_phone: str,
    address: str | None,
    delivery_type: str | None,
    currency: str = "EUR",
) -> Order:
    """
    Создать заказ на основании текущей активной корзины пользователя.

    Бросает ValueError, если корзина пуста.
    """
    logger.info(
        "order_service.create_order_from_cart: user_id=%s name='%s' phone='%s' delivery=%s",
        user_id, contact_name, contact_phone, delivery_type
    )
    try:
        async with session.begin():
            order = await OrderRepo.create_from_cart(
                session,
                user_id=user_id,
                contact_name=contact_name,
                contact_phone=contact_phone,
                address=address,
                delivery_type=delivery_type,
                currency=currency,
            )
        logger.info("order_service.create_order_from_cart: CREATED order_id=%s number=%s", order.id, order.order_number)
        return order
    except ValueError:
        logger.warning("order_service.create_order_from_cart: empty cart user_id=%s", user_id)
        raise


async def get_order(session: AsyncSession, order_id: int) -> Optional[Order]:
    """Получить заказ по id (с позициями)."""
    logger.debug("order_service.get_order: order_id=%s", order_id)
    return await OrderRepo.get(session, order_id)


async def list_orders_for_admin(session: AsyncSession, *, limit: int = 50, offset: int = 0) -> List[Order]:
    """Список заказов для админ-панели."""
    logger.debug("order_service.list_orders_for_admin: limit=%s offset=%s", limit, offset)
    return await OrderRepo.list_for_admin(session, limit=limit, offset=offset)


async def set_order_status(session: AsyncSession, *, order_id: int, status: OrderStatus) -> Optional[Order]:
    """Изменить статус заказа (вернёт обновлённый объект или None)."""
    logger.info("order_service.set_order_status: order_id=%s -> %s", order_id, status.value)
    async with session.begin():
        order = await OrderRepo.set_status(session, order_id, status)
    if order is None:
        logger.warning("order_service.set_order_status: order not found order_id=%s", order_id)
    return order
