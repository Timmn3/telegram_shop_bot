"""
Инлайн-клавиатуры и текст для корзины.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from app.db.models import CartItem


def render_cart_text(items: Iterable[CartItem], total: Decimal) -> str:
    """
    Формирует текст корзины с позициями и общей суммой.
    """
    items = list(items)
    if not items:
        return "🛒 Ваша корзина пуста."

    lines = ["🛒 <b>Корзина</b>:", ""]
    currency = items[0].product.currency if items and items[0].product else "RUB"

    for it in items:
        title = it.product.title if it.product else f"Товар #{it.product_id}"
        item_sum = (it.price_at_added or Decimal("0")) * it.quantity
        lines.append(f"• {title} — {it.quantity} шт × {it.price_at_added} = <b>{item_sum}</b> {currency}")
    lines.append("")
    lines.append(f"Итого: <b>{total}</b> {currency}")
    return "\n".join(lines)


def build_cart_keyboard(items: Iterable[CartItem]) -> InlineKeyboardMarkup:
    """
    Клавиатура корзины:
    - Для каждой позиции: [-] qty [+] и 🗑 удалить
    - Внизу: Очистить | Оформить
    """
    items = list(items)
    kb = InlineKeyboardBuilder()

    if not items:
        # Пустая корзина: только кнопка "Назад в меню" / "Каталог"
        kb.button(text="⬅️ В каталог", callback_data="cart:back_to_menu")
        kb.adjust(1)
        return kb.as_markup()

    # Кнопки по позициям
    for it in items:
        title = it.product.title if it.product else f"Товар #{it.product_id}"
        # отдельная строка — заголовок товара
        kb.button(text=f"• {title}", callback_data="noop")
        # строка управления количеством
        kb.button(text="➖", callback_data=f"cart:dec:{it.product_id}")
        kb.button(text=f"{it.quantity} шт", callback_data="noop")
        kb.button(text="➕", callback_data=f"cart:inc:{it.product_id}")
        # удаление
        kb.button(text="🗑 Удалить", callback_data=f"cart:del:{it.product_id}")
        kb.adjust(1, 3, 1)  # по строкам: заголовок / - qty + / удалить

    # Низ: очистить / оформить
    kb.button(text="🧹 Очистить", callback_data="cart:clear")
    kb.button(text="🛍 Оформить", callback_data="checkout:start")
    kb.adjust(2)
    return kb.as_markup()
