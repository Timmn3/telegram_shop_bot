"""
Проверка создания заказа из корзины:
- формируется order_number
- создаются order_items
- корзина очищается и помечается ORDERED
"""
from decimal import Decimal
import pytest
from sqlalchemy import insert, select

from app.db.models import User, Category, Product, Cart, CartStatus, OrderItem
from app.services.cart_service import add_item
from app.services.order_service import create_order_from_cart


@pytest.mark.asyncio
async def test_create_order_from_cart(async_session):
    # Arrange: пользователь, продукт, добавим в корзину 3шт
    async with async_session.begin():
        await async_session.execute(insert(User).values(id=222, full_name="Buyer"))
        cat_id = (await async_session.execute(insert(Category).values(title="Смартфоны").returning(Category.id))).scalar_one()
        await async_session.execute(
            insert(Product).values(
                title="Phone Z",
                description="Смартфон Z",
                price=Decimal("333.00"),
                currency="EUR",
                category_id=cat_id,
                is_active=True,
            )
        )
        product_id = (await async_session.execute(select(Product.id))).scalar_one()

    await add_item(async_session, user_id=222, product_id=product_id, quantity=2)
    await add_item(async_session, user_id=222, product_id=product_id, quantity=1)

    # Act
    order = await create_order_from_cart(
        async_session,
        user_id=222,
        contact_name="Buyer Name",
        contact_phone="+123456",
        address="Address 1",
        delivery_type="courier",
        currency="EUR",
    )

    # Assert: номер формата ORDER-YYYYMMDD-<id>
    assert order.order_number.startswith("ORDER-")
    assert order.total_amount == Decimal("999.00")  # 3 * 333.00

    # Проверим, что корзина очищена и статус ORDERED
    async with async_session.begin():
        cart = (await async_session.execute(select(Cart).where(Cart.user_id == 222))).scalar_one()
        assert cart.status == CartStatus.ORDERED
        items_count = (await async_session.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars().all()
        assert len(items_count) == 1  # один вид товара
