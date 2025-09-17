"""
Каталог:
- Показ категорий (root и дочерние) — по колбэку.
- Показ списка товаров в категории — пагинация.
- Показ карточки товара.
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory
from app.services.catalog_service import (
    list_child_categories,
    list_products,
    get_product,
)
from app.bot.keyboards.inline_catalog import (
    CatCB,
    ProdListCB,
    ProdCB,
    build_categories_kb,
    build_products_kb,
    build_product_card_kb,
)

catalog_router = Router(name="catalog")


# --- Просмотр дочерних категорий по выбранной категории ---
@catalog_router.callback_query(CatCB.filter())
async def on_category_selected(callback: CallbackQuery, callback_data: CatCB) -> None:
    """
    Пользователь выбрал категорию (root или любую другую).
    Показываем либо дочерние категории, либо сразу товары, если дочерних нет.
    """
    cat_id = callback_data.cat_id
    async with AsyncSessionFactory() as session:
        children = await list_child_categories(session, parent_id=cat_id)

        if children:
            kb = build_categories_kb(children)
            await callback.message.edit_text("🔹 Подкатегории:", reply_markup=kb)
        else:
            # Если нет подкатегорий — сразу показываем список товаров
            kb = await _build_products_keyboard(session, category_id=cat_id, page=0, page_size=6)
            await callback.message.edit_text("🛍 Товары:", reply_markup=kb)

    await callback.answer()


# --- Просмотр списка товаров с пагинацией ---
@catalog_router.callback_query(ProdListCB.filter())
async def on_products_page(callback: CallbackQuery, callback_data: ProdListCB) -> None:
    """
    Переключение страниц со списком товаров в категории.
    """
    async with AsyncSessionFactory() as session:
        kb = await _build_products_keyboard(
            session,
            category_id=callback_data.cat_id,
            page=callback_data.page,
            page_size=callback_data.page_size,
        )
    await callback.message.edit_text("🛍 Товары:", reply_markup=kb)
    await callback.answer()


# --- Просмотр карточки товара ---
@catalog_router.callback_query(ProdCB.filter())
async def on_product_open(callback: CallbackQuery, callback_data: ProdCB) -> None:
    """
    Открыть карточку товара.
    """
    product_id = callback_data.product_id
    async with AsyncSessionFactory() as session:
        product = await get_product(session, product_id=product_id)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    caption = (
        f"<b>{product.title}</b>\n"
        f"Цена: {product.price} {product.currency}\n\n"
        f"{product.description or '—'}"
    )

    kb = build_product_card_kb(product_id=product.id)
    # На этом этапе отправляем как текст (фото добавим позже, когда подключим хранилище file_id/url)
    await callback.message.edit_text(caption, reply_markup=kb)
    await callback.answer()


# --- Вспомогательное построение клавиатуры списка товаров ---
async def _build_products_keyboard(session: AsyncSession, *, category_id: int, page: int, page_size: int):
    """
    Собирает InlineKeyboardMarkup для списка товаров с пагинацией.

    :param category_id: категория
    :param page: номер страницы (0..N)
    :param page_size: размер страницы
    """
    offset = max(0, page) * page_size
    products = await list_products(session, category_id=category_id, limit=page_size, offset=offset)

    # Чтобы понимать, есть ли следующая страница, возьмём +1 элемент
    products_nextcheck = await list_products(session, category_id=category_id, limit=page_size + 1, offset=offset)
    has_next = len(products_nextcheck) > page_size
    has_prev = page > 0

    return build_products_kb(
        products=products,
        category_id=category_id,
        page=page,
        page_size=page_size,
        has_prev=has_prev,
        has_next=has_next,
    )
