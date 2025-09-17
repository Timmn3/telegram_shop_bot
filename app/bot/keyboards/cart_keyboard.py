"""
Инлайн-клавиатуры и текст для корзины.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.db.models import CartItem

NOOP = "noop"


# ─────────────────────────── Утилиты отображения ─────────────────────────── #

def _crop_title(title: str, limit: int = 24) -> str:
    """
    Обрезает длинные названия товаров, чтобы строка не «распухала» в одну кнопку.
    Пример: "Очень длинное название…" → "Очень длинное назв…"
    """
    t = (title or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1].rstrip() + "…"


def render_cart_text(items: List[CartItem], total: Decimal) -> str:
    """
    Собирает текст корзины (шапка + позиции + итог).
    Не зависит от клавиатуры.
    """
    if not items:
        return "🧺 Корзина пуста."

    lines = ["🧺 <b>Корзина:</b>"]
    for it in items:
        item_total = (it.price_at_added or Decimal("0")) * it.quantity
        lines.append(
            f"• {it.product.title} — {it.quantity} шт × {it.price_at_added} = <b>{item_total}</b> {it.product.currency}"
        )
    lines.append(f"\nИтого: <b>{total}</b> {items[0].product.currency}")
    return "\n".join(lines)


# ─────────────────────────── Основная клавиатура ─────────────────────────── #

def build_cart_keyboard(items: List[CartItem]) -> InlineKeyboardMarkup:
    """
    Построить инлайн-клавиатуру корзины c компактными строками по товару.
    Каждая позиция занимает одну строку: [• title] [➖] [qty] [➕] [🗑]
    Внизу — отдельные широкие кнопки «Очистить» и «Оформить».
    Для пустой корзины — только «⬅️ В каталог».
    """
    kb: list[list[InlineKeyboardButton]] = []

    if not items:
        kb.append([InlineKeyboardButton(text="⬅️ В каталог", callback_data="cart:back_to_menu")])
        return InlineKeyboardMarkup(inline_keyboard=kb)

    for it in items:
        pid = it.product_id
        title_btn = InlineKeyboardButton(text=f"• {_crop_title(it.product.title)}", callback_data=NOOP)
        dec_btn = InlineKeyboardButton(text="➖", callback_data=f"cart:dec:{pid}")
        qty_btn = InlineKeyboardButton(text=str(it.quantity), callback_data=NOOP)
        inc_btn = InlineKeyboardButton(text="➕", callback_data=f"cart:inc:{pid}")
        del_btn = InlineKeyboardButton(text="🗑", callback_data=f"cart:del:{pid}")
        kb.append([title_btn, dec_btn, qty_btn, inc_btn, del_btn])

    # Разделяем визуально товары и нижний блок
    # (телеграм не имеет «разделителей», просто новой строкой ниже добавим большие кнопки)
    kb.append([InlineKeyboardButton(text="🧹 Очистить корзину", callback_data="cart:clear")])
    kb.append([InlineKeyboardButton(text="🛍 Оформить", callback_data="checkout:start")])

    return InlineKeyboardMarkup(inline_keyboard=kb)