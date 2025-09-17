"""
Инлайн-клавиатуры каталога и декларации callback-data.

Включает:
- CatCB: выбор категории.
- ProdListCB: пагинация товаров (категория, страница, размер страницы).
- ProdCB: переход к карточке товара.
"""
from __future__ import annotations

from typing import Iterable
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

from app.db.models import Category, Product


# --- CallbackData схемы ---
class CatCB(CallbackData, prefix="cat"):
    """Выбор категории."""
    cat_id: int


class ProdListCB(CallbackData, prefix="plist"):
    """Пагинация по товарам."""
    cat_id: int
    page: int
    page_size: int


class ProdCB(CallbackData, prefix="prod"):
    """Открыть карточку товара."""
    product_id: int


# --- Клавиатуры ---
def build_categories_kb(categories: Iterable[Category]) -> InlineKeyboardMarkup:
    """
    Список категорий (кнопка на категорию).
    Если категорий нет — вернётся клавиатура с одной кнопкой-заглушкой.
    """
    kb = InlineKeyboardBuilder()
    has_any = False
    for c in categories:
        has_any = True
        kb.button(text=f"📁 {c.title}", callback_data=CatCB(cat_id=c.id))
    if not has_any:
        kb.button(text="Пусто", callback_data="noop")
    kb.adjust(1)
    return kb.as_markup()


def build_products_kb(
    *,
    products: Iterable[Product],
    category_id: int,
    page: int,
    page_size: int,
    has_prev: bool,
    has_next: bool,
) -> InlineKeyboardMarkup:
    """
    Список товаров с пагинацией.
    На каждый товар — кнопка с переходом в карточку.
    Внизу — пагинация (◀️ / ▶️).
    """
    kb = InlineKeyboardBuilder()

    # Кнопки товаров
    for p in products:
        price = f"{p.price} {p.currency}"
        kb.button(text=f"🛒 {p.title} — {price}", callback_data=ProdCB(product_id=p.id))

    if not list(products):
        kb.button(text="Нет товаров", callback_data="noop")

    # Пагинация
    nav = InlineKeyboardBuilder()
    if has_prev:
        nav.button(text="◀️", callback_data=ProdListCB(cat_id=category_id, page=page - 1, page_size=page_size))
    nav.button(text=f"Стр. {page + 1}", callback_data="noop")
    if has_next:
        nav.button(text="▶️", callback_data=ProdListCB(cat_id=category_id, page=page + 1, page_size=page_size))

    kb.adjust(1)
    kb = InlineKeyboardBuilder(markup=kb.as_markup())
    kb.attach(nav)
    return kb.as_markup()


def build_product_card_kb(*, product_id: int) -> InlineKeyboardMarkup:
    """
    Кнопки под карточкой товара.
    Сейчас: только "В корзину" (добавим обработчик в модуле корзины на следующем шаге).
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ В корзину", callback_data=f"cart:add:{product_id}")
    kb.button(text="⬅️ Назад к товарам", callback_data="noop")
    kb.adjust(1, 1)
    return kb.as_markup()
