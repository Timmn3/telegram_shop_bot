import pytest

from app.services import order_service


@pytest.mark.asyncio
async def test_create_order_from_empty_cart_raises(async_session):
    """
    Создание заказа с пустой корзиной должно приводить к ValueError.
    """
    with pytest.raises(ValueError):
        await order_service.create_order_from_cart(
            async_session,
            user_id=444,  # корзина пустая
            contact_name="Empty User",
            contact_phone="+79991112233",
            address=None,
            delivery_type="pickup",
            currency="EUR",
        )
