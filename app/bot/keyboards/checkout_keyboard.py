"""
Клавиатуры и предпросмотр для Checkout FSM.

Содержит:
- build_cancel_kb(include_back): клавиатура «Отмена» + (опц.) «Назад»
- build_delivery_kb(include_back): выбор способа доставки + (опц.) «Назад»
- build_confirm_kb(include_back): подтверждение заказа + «Назад»/«Отмена»
- render_order_preview(...): текстовая сводка заказа перед подтверждением
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Псевдомодели для подсказок типов (реальные импортировать не нужно)
class _CartItem:
    product_title: str
    quantity: int
    price: Decimal
    currency: str


# ─────────────────────────── Клавиатуры ─────────────────────────── #

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
    Варианты можно расширить под проект.
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
    kb = InlineKeyboardBuilder(markup=kb.as_markup())
    kb.attach(nav)
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


# ─────────────────────────── Предпросмотр ─────────────────────────── #

def render_order_preview(
    *,
    items: Iterable[_CartItem],
    total: Decimal,
    contact_name: str,
    contact_phone: str,
    address: Optional[str],
    delivery_type: str,
) -> str:
    """
    Сформировать текст подтверждения заказа.

    Параметры:
    - items: позиции корзины (title, qty, price)
    - total: сумма
    - contact_name: имя клиента
    - contact_phone: телефон
    - address: адрес доставки или None (самовывоз)
    - delivery_type: тип доставки (courier/pickup/post и пр.)

    Возвращает:
    - Готовую разметку (HTML), пригодную для message.answer(...)
    """
    lines = ["<b>Проверьте заказ</b>", ""]
    currency = None

    # Список позиций
    found = False
    for it in items:
        found = True
        currency = currency or getattr(it, "currency", "EUR")
        title = getattr(it, "product_title", "")
        qty = getattr(it, "quantity", 1)
        price = getattr(it, "price", 0)
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
