# app/bot/keyboards/inline_catalog.py
"""
Инлайн-клавиатуры каталога и декларации callback-data.

Включает:
- CatCB: выбор категории.
- ProdListCB: пагинация товаров (категория, страница, размер страницы).
- ProdOpenCB: открытие карточки товара с контекстом возвращения.
- ProdCB: (совместимость) открытие карточки товара без контекста.
"""
from __future__ import annotations

from typing import Iterable, Optional
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

from app.db.models import Category, Product


class CatCB(CallbackData, prefix="cat"):
    """Выбор категории."""
    cat_id: int


class ProdListCB(CallbackData, prefix="plist"):
    """Пагинация по товарам."""
    cat_id: int
    page: int
    page_size: int


class ProdOpenCB(CallbackData, prefix="prodo"):
    """
    Открыть карточку товара с контекстом:
    - product_id — товар,
    - cat_id/page/page_size — чтобы знать, куда вернуться кнопкой «Назад к товарам».
    """
    product_id: int
    cat_id: int
    page: int
    page_size: int


class ProdCB(CallbackData, prefix="prod"):
    """
    Открыть карточку товара (устаревший вариант без контекста).
    Оставлен для совместимости, но в списке товаров использовать ProdOpenCB.
    """
    product_id: int


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

    ВАЖНО: не оборачиваем готовый InlineKeyboardMarkup в новый билдер!
    Склейка билдера с навигацией делается через .attach(nav) до .as_markup().
    """
    kb = InlineKeyboardBuilder()

    prods = list(products)
    for p in prods:
        price = f"{p.price} {p.currency}"
        kb.button(
            text=f"🛒 {p.title} — {price}",
            callback_data=ProdOpenCB(
                product_id=p.id,
                cat_id=category_id,
                page=page,
                page_size=page_size,
            ),
        )

    if not prods:
        kb.button(text="Нет товаров", callback_data="noop")

    # Пагинация
    nav = InlineKeyboardBuilder()
    if has_prev:
        nav.button(
            text="◀️",
            callback_data=ProdListCB(cat_id=category_id, page=page - 1, page_size=page_size),
        )
    nav.button(text=f"Стр. {page + 1}", callback_data="noop")
    if has_next:
        nav.button(
            text="▶️",
            callback_data=ProdListCB(cat_id=category_id, page=page + 1, page_size=page_size),
        )

    kb.adjust(1)
    kb.attach(nav)  # <-- фикс: прикрепляем билдер, не InlineKeyboardMarkup
    return kb.as_markup()


def build_product_card_kb(
    *,
    product_id: int,
    back_to: Optional[ProdListCB] = None,
) -> InlineKeyboardMarkup:
    """
    Кнопки под карточкой товара.

    Параметры:
    - product_id: ID товара (для «В корзину»).
    - back_to: ProdListCB с контекстом возврата (категория/страница); если не задан — будет noop.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ В корзину", callback_data=f"cart:add:{product_id}")
    if back_to is not None:
        kb.button(text="⬅️ Назад к товарам", callback_data=back_to.pack())
    else:
        kb.button(text="⬅️ Назад к товарам", callback_data="noop")
    kb.adjust(1, 1)
    return kb.as_markup()
