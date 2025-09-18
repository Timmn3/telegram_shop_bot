import pytest
from decimal import Decimal
from sqlalchemy import insert, select

from app.db.models import User, Category, Product, OrderStatus, Order
from app.services import cart_service, order_service
from app.db.repository import OrderRepo


@pytest.mark.asyncio
async def test_admin_change_order_status(async_session):
    """
    Смена статуса заказа админом:
    1) Готовим пользователя и товар.
    2) Кладём товар в корзину и создаём заказ из корзины.
    3) Меняем статус через OrderRepo.set_status(..., OrderStatus.processing).
    4) Проверяем, что статус обновлён в БД.
    """
    # Arrange: user + product
    async with async_session.begin():
        await async_session.execute(insert(User).values(id=333, full_name="Admin Status User"))
        cat_id = (await async_session.execute(
            insert(Category).values(title="Категория Y").returning(Category.id)
        )).scalar_one()
        await async_session.execute(insert(Product).values(
            title="Товар Y",
            description="Описание",
            price=Decimal("50.00"),
            currency="EUR",
            category_id=cat_id,
            is_active=True,
        ))
        product_id = (await async_session.execute(select(Product.id))).scalar_one()

    # В корзину → создать заказ
    await cart_service.add_item(async_session, user_id=333, product_id=product_id, quantity=1)
    order = await order_service.create_order_from_cart(
        async_session,
        user_id=333,
        contact_name="User",
        contact_phone="+79990000000",
        address="Город, Улица 1",
        delivery_type="courier",
        currency="EUR",
    )
    assert order.status == OrderStatus.NEW

    # Действие админа: смена статуса
    updated = await OrderRepo.set_status(async_session, order_id=order.id, status=OrderStatus.PROCESSING)
    assert updated is not None
    assert updated.status == OrderStatus.PROCESSING

    # Перечитать напрямую из БД
    row = (await async_session.execute(select(Order).where(Order.id == order.id))).scalar_one()
    assert row.status == OrderStatus.PROCESSING
