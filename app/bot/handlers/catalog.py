"""
Хэндлеры каталога с поддержкой мультифото в карточке товара.

Изменения:
- Если у товара более 1 фото — отправляем альбом (media group) до 10 фото.
- Подпись (caption) ставим на первое фото; следом отдельным сообщением отдаём клавиатуру
  «В корзину / Назад к товарам», чтобы не терять её после альбома.

Совместимо с:
- ProdOpenCB (контекст cat/page/page_size) — рекомендовано
- ProdCB (устаревший) — кнопка «Назад» будет noop
"""
from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory
from app.services.catalog_service import list_child_categories, list_products, get_product
from app.bot.keyboards.inline_catalog import (
    CatCB,
    ProdListCB,
    ProdCB,
    ProdOpenCB,
    build_categories_kb,
    build_products_kb,
    build_product_card_kb,
)

catalog_router = Router(name="catalog")


@catalog_router.callback_query(CatCB.filter())
async def on_category_selected(callback: CallbackQuery, callback_data: CatCB) -> None:
    """Категория → подкатегории или сразу товары."""
    category_id = callback_data.cat_id
    async with AsyncSessionFactory() as session:
        children = await list_child_categories(session, parent_id=category_id)
        if children:
            kb = build_categories_kb(children)
            await callback.message.edit_text("🔹 Подкатегории:", reply_markup=kb)
        else:
            kb = await _build_products_keyboard(session, category_id=category_id, page=0, page_size=6)
            await callback.message.edit_text("🛍 Товары:", reply_markup=kb)
    await callback.answer()


@catalog_router.callback_query(ProdListCB.filter())
async def on_products_page(callback: CallbackQuery, callback_data: ProdListCB) -> None:
    """Пагинация списка товаров."""
    async with AsyncSessionFactory() as session:
        kb = await _build_products_keyboard(
            session,
            category_id=callback_data.cat_id,
            page=callback_data.page,
            page_size=callback_data.page_size,
        )
    await callback.message.edit_text("🛍 Товары:", reply_markup=kb)
    await callback.answer()


@catalog_router.callback_query(ProdOpenCB.filter())
async def on_product_open_with_ctx(callback: CallbackQuery, callback_data: ProdOpenCB) -> None:
    """
    Карточка товара с контекстом возврата.
    Если фото > 1 — отправляем альбом (до 10 штук).
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
    back_cb = ProdListCB(cat_id=callback_data.cat_id, page=callback_data.page, page_size=callback_data.page_size)
    kb = build_product_card_kb(product_id=product.id, back_to=back_cb)

    # Фото
    images = list(product.images or [])
    if not images:
        await callback.message.answer(caption, reply_markup=kb)
        await callback.answer()
        return

    # Сформировать список медиа (до 10)
    media = []
    for idx, img in enumerate(images[:10]):
        media.append(
            InputMediaPhoto(
                media=img.telegram_file_id or img.url,
                caption=caption if idx == 0 else None,
                parse_mode="HTML" if idx == 0 else None,
            )
        )

    # Отправляем альбом и следом — клавиатуру отдельным сообщением
    await callback.message.answer_media_group(media=media)
    await callback.message.answer("Выберите действие:", reply_markup=kb)
    await callback.answer()


@catalog_router.callback_query(ProdCB.filter())
async def on_product_open_legacy(callback: CallbackQuery, callback_data: ProdCB) -> None:
    """Карточка товара без контекста (legacy)."""
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
    kb = build_product_card_kb(product_id=product.id, back_to=None)

    images = list(product.images or [])
    if not images:
        await callback.message.answer(caption, reply_markup=kb)
        await callback.answer()
        return

    if len(images) == 1:
        img = images[0]
        await callback.message.answer_photo(
            photo=img.telegram_file_id or img.url,
            caption=caption,
            reply_markup=kb,
        )
        await callback.answer()
        return

    media = []
    for idx, img in enumerate(images[:10]):
        media.append(
            InputMediaPhoto(
                media=img.telegram_file_id or img.url,
                caption=caption if idx == 0 else None,
                parse_mode="HTML" if idx == 0 else None,
            )
        )
    await callback.message.answer_media_group(media=media)
    await callback.message.answer("Выберите действие:", reply_markup=kb)
    await callback.answer()


# ─────────────────────────────────────────────────────────────

from sqlalchemy.ext.asyncio import AsyncSession  # ниже используется


async def _build_products_keyboard(session: AsyncSession, *, category_id: int, page: int, page_size: int):
    """Собрать клавиатуру списка товаров с пагинацией."""
    offset = max(0, page) * page_size
    products = await list_products(session, category_id=category_id, limit=page_size, offset=offset)
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


# --- Назад к корневым категориям ---
from aiogram import F
from aiogram.types import CallbackQuery
from app.db.session import AsyncSessionFactory
from app.services.catalog_service import list_root_categories
from app.bot.keyboards.inline_catalog import build_categories_kb

@catalog_router.callback_query(F.data == "back:categories")
async def cb_back_to_categories(callback: CallbackQuery) -> None:
    """
    Возврат на экран корневых категорий:
    показывает «🗂 Выберите категорию:» и клавиатуру категорий.
    """
    async with AsyncSessionFactory() as session:
        categories = await list_root_categories(session)
    kb = build_categories_kb(categories)
    if callback.message:
        await callback.message.edit_text("🗂 Выберите категорию:", reply_markup=kb)
    await callback.answer()
