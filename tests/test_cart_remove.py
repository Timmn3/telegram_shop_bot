import pytest
from decimal import Decimal
from sqlalchemy import insert, select

from app.db.models import User, Category, Product
from app.services import cart_service


@pytest.mark.asyncio
async def test_remove_item_from_cart(async_session):
    """
    Удаление позиции из корзины:
    1) Готовим пользователя, категорию и товар.
    2) Добавляем товар в корзину (qty=2).
    3) Удаляем позицию cart_service.remove_item().
    4) Проверяем: корзина пуста, subtotal == 0.
    """
    async with async_session.begin():
        await async_session.execute(insert(User).values(id=222, full_name="Cart Remove User"))
        cat_id = (await async_session.execute(
            insert(Category).values(title="Категория X").returning(Category.id)
        )).scalar_one()
        await async_session.execute(insert(Product).values(
            title="Товар X",
            description="Описание",
            price=Decimal("100.00"),
            currency="EUR",
            category_id=cat_id,
            is_active=True,
        ))
        product_id = (await async_session.execute(select(Product.id))).scalar_one()

    # add → remove
    await cart_service.add_item(async_session, user_id=222, product_id=product_id, quantity=2)
    items_before = await cart_service.list_items(async_session, user_id=222)
    assert items_before and items_before[0].quantity == 2

    await cart_service.remove_item(async_session, user_id=222, product_id=product_id)

    items_after = await cart_service.list_items(async_session, user_id=222)
    total_after = await cart_service.subtotal(async_session, user_id=222)
    assert items_after == []
    assert total_after == Decimal("0")
