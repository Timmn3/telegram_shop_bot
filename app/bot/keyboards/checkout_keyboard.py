"""
Клавиатуры и предпросмотр для Checkout FSM.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class _CartItem:
    """Псевдомодель для подсказок типов (для текста предпросмотра)."""
    product_title: str
    quantity: int
    price: Decimal
    currency: str


def build_cancel_kb(*, include_back: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура для шагов ввода текста.
    - «⬅️ Назад» (если include_back=True)
    - «🚫 Отмена»
    """
    kb = InlineKeyboardBuilder()
    if include_back:
        kb.button(text="⬅️ Назад", callback_data="checkout:back")
    kb.button(text="🚫 Отмена", callback_data="checkout:cancel")
    kb.adjust(1, 1) if include_back else kb.adjust(1)
    return kb.as_markup()


def build_delivery_kb(*, include_back: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора способа доставки.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="🚚 Курьер", callback_data="delivery:courier")
    kb.button(text="🏬 Самовывоз", callback_data="delivery:pickup")
    kb.button(text="✉️ Почта", callback_data="delivery:post")

    nav = InlineKeyboardBuilder()
    if include_back:
        nav.button(text="⬅️ Назад", callback_data="checkout:back")
    nav.button(text="🚫 Отмена", callback_data="checkout:cancel")

    kb.adjust(1)
    kb.attach(nav)  # <-- FIX: attach вместо InlineKeyboardBuilder(markup=...)
    return kb.as_markup()


def build_confirm_kb(*, include_back: bool = True) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения заказа.
    По умолчанию содержит «Назад» и «Отмена», плюс «✅ Подтвердить».
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="checkout:confirm")
    if include_back:
        kb.button(text="⬅️ Назад", callback_data="checkout:back")
    kb.button(text="🚫 Отмена", callback_data="checkout:cancel")
    kb.adjust(1, 2) if include_back else kb.adjust(1, 1)
    return kb.as_markup()


def render_order_preview(
    *,
    items: Iterable[_CartItem],
    total: Decimal,
    contact_name: str,
    contact_phone: str,
    address: Optional[str],
    delivery_type: str,
) -> str:
    """Сформировать HTML-разметку подтверждения заказа для сообщения."""
    lines = ["<b>Проверьте заказ</b>", ""]

    currency = None
    found = False
    for it in items:
        found = True
        # сначала пробуем у CartItem/OrderItem product.title, иначе у псевдомодели
        title = getattr(it, "product", None).title if getattr(it, "product", None) else getattr(it, "product_title", "")
        qty = getattr(it, "quantity", 1)
        currency = currency or getattr(it, "currency", getattr(it.product, "currency", "EUR"))
        lines.append(f"• {title} × {qty}")

    if not found:
        lines.append("— (пусто) —")

    lines += [
        "",
        f"<b>Итого:</b> {total} {currency or 'EUR'}",
        "",
        f"<b>Имя:</b> {contact_name}",
        f"<b>Телефон:</b> {contact_phone}",
        f"<b>Адрес:</b> {address if address else 'самовывоз'}",
        f"<b>Доставка:</b> {delivery_type}",
        "",
        "Если всё верно — подтвердите заказ.",
    ]
    return "\n".join(lines)

