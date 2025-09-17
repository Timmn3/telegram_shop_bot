"""
Проверка генерации номера заказа.
"""
import datetime
import pytest

from app.db.repository import OrderRepo


@pytest.mark.asyncio
async def test_generate_order_number_format():
    ts = datetime.datetime(2025, 1, 2, 3, 4, 5)
    number = await OrderRepo.generate_order_number(order_id=42, created_at=ts)
    assert number == "ORDER-20250102-42"
