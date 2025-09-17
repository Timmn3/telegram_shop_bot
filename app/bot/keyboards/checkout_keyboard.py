"""
Клавиатуры и рендеры для оформления заказа.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from app.db.models import CartItem


def build_cancel_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены оформления."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🚫 Отмена", callback_data="checkout:cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_delivery_kb() -> InlineKeyboardMarkup:
    """Выбор способа доставки."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🚚 Курьер", callback_data="delivery:courier")
    kb.button(text="🏬 Самовывоз", callback_data="delivery:pickup")
    kb.adjust(2)
    # Добавим отмену на всякий
    kb.button(text="🚫 Отмена", callback_data="checkout:cancel")
    kb.adjust(2, 1)
    return kb.as_markup()


def build_confirm_kb() -> InlineKeyboardMarkup:
    """Подтверждение оформления."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="checkout:confirm")
    kb.button(text="🚫 Отмена", callback_data="checkout:cancel")
    kb.adjust(2)
    return kb.as_markup()


def render_order_preview(
    *,
    items: Iterable[CartItem],
    total: Decimal,
    contact_name: str,
    contact_phone: str,
    address: str | None,
    delivery_type: str | None,
) -> str:
    """Формирует текст предварительного просмотра заказа."""
    lines = ["<b>Проверьте данные заказа:</b>", ""]
    currency = "EUR"
    for it in items:
        if it.product:
            currency = it.product.currency
            title = it.product.title
        else:
            title = f"Товар #{it.product_id}"
        item_sum = (it.price_at_added or Decimal("0")) * it.quantity
        lines.append(f"• {title} — {it.quantity} × {it.price_at_added} = <b>{item_sum}</b> {currency}")
    lines += [
        "",
        f"Итого: <b>{total}</b> {currency}",
        "",
        f"Имя: <b>{contact_name}</b>",
        f"Телефон: <b>{contact_phone}</b>",
        f"Адрес: <b>{address or '—'}</b>",
        f"Доставка: <b>{delivery_type or '—'}</b>",
        "",
        "Нажмите «Подтвердить», чтобы оформить заказ.",
    ]
    return "\n".join(lines)
