from decimal import Decimal

import pytest
from sqlalchemy import insert, select

from app.db.models import User, Category, Product
from app.services.cart_service import add_item, list_items, subtotal


@pytest.mark.asyncio
async def test_add_and_subtotal(async_session):
    """
    Проверяет:
    - добавление двух одинаковых товаров в корзину;
    - агрегацию количества до 2;
    - корректный подсчёт subtotal.
    """
    # Arrange: создаём пользователя, категорию и товар
    async with async_session.begin():
        await async_session.execute(
            insert(User).values(id=111, full_name="Test User")
        )
        res = await async_session.execute(
            insert(Category).values(title="Ноутбуки").returning(Category.id)
        )
        category_id = res.scalar_one()
        await async_session.execute(
            insert(Product).values(
                title="Laptop X",
                description="Тестовый ноутбук",
                price=Decimal("999.90"),   # <-- раньше было 9999.90, из-за чего subtotal x10
                currency="RUB",
                category_id=category_id,
                is_active=True,
            )
        )
        # получим id продукта
        pid = (await async_session.execute(select(Product.id))).scalar_one()

    # Act: добавляем 2 шт и считаем сумму
    await add_item(async_session, user_id=111, product_id=pid, quantity=1)
    await add_item(async_session, user_id=111, product_id=pid, quantity=1)

    items = await list_items(async_session, user_id=111)
    total = await subtotal(async_session, user_id=111)

    # Assert
    assert len(items) == 1
    assert items[0].quantity == 2
    assert total == Decimal("1999.80")
