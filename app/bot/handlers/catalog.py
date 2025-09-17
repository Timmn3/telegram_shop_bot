"""
Модуль хэндлеров каталога.

Назначение
---------
Отвечает за навигацию по дереву категорий, показ списков товаров с пагинацией
и отображение карточки товара. В карточке товара — поддержка фото (telegram_file_id или url)
и корректная кнопка «Назад к товарам» с восстановлением страницы категории.

Основные сценарии
-----------------
1) Пользователь открывает корневые категории из /menu (хэндлер в common.py).
   По нажатию на категорию (CatCB) показываем подкатегории либо сразу товары.

2) Пользователь листает товары в категории (ProdListCB) — пагинация «вперёд/назад».

3) Пользователь открывает карточку товара:
   - Через ProdOpenCB (рекомендуемо): карточка получает контекст возврата (cat/page/page_size).
   - Через ProdCB (устаревший путь): карточка без контекста (кнопка «назад» будет noop).

Архитектура
-----------
- Сервисный слой: app/services/catalog_service.py
- Репозитории: через сервисы вызывают ProductRepo/CategoryRepo
- Сессии: создаём из AsyncSessionFactory()

Исключения и ошибки
-------------------
- Если товар не найден — показываем alert в callback.
- После каждого действия вызываем callback.answer() чтобы скрыть «часики».
"""

from aiogram import Router
from aiogram.types import CallbackQuery
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
    ProdCB,       # совместимость
    ProdOpenCB,   # новый вариант с контекстом
    build_categories_kb,
    build_products_kb,
    build_product_card_kb,
)

catalog_router = Router(name="catalog")


@catalog_router.callback_query(CatCB.filter())
async def on_category_selected(callback: CallbackQuery, callback_data: CatCB) -> None:
    """
    Пользователь нажал на категорию.

    Логика:
    1) Ищем дочерние категории.
    2) Если дочерние есть — показываем их списком.
    3) Если дочерних нет — показываем товары этой категории (страница 1).

    UI:
    - Сообщение редактируем через edit_text() с новым reply_markup.
    """
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
    """
    Пользователь листает список товаров (пагинация).

    Параметры:
    - cat_id: ID категории
    - page: номер страницы (0..N)
    - page_size: количество товаров на страницу

    Действия:
    - Пересобираем клавиатуру товаров, считаем наличие «следующей» страницы,
      обновляем текст сообщения (edit_text).
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


@catalog_router.callback_query(ProdOpenCB.filter())
async def on_product_open_with_ctx(callback: CallbackQuery, callback_data: ProdOpenCB) -> None:
    """
    Открыть карточку товара с контекстом возврата на список товаров.

    Аргументы:
    - callback_data.product_id: ID товара.
    - callback_data.cat_id/page/page_size: откуда пришли (для кнопки «Назад к товарам»).
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

    # Отображаем фото (если есть)
    if product.images:
        img = product.images[0]
        if getattr(img, "telegram_file_id", None):
            await callback.message.answer_photo(
                photo=img.telegram_file_id,
                caption=caption,
                reply_markup=kb,
            )
        elif getattr(img, "url", None):
            await callback.message.answer_photo(
                photo=img.url,
                caption=caption,
                reply_markup=kb,
            )
        else:
            await callback.message.answer(caption, reply_markup=kb)
    else:
        await callback.message.answer(caption, reply_markup=kb)

    await callback.answer()


@catalog_router.callback_query(ProdCB.filter())
async def on_product_open(callback: CallbackQuery, callback_data: ProdCB) -> None:
    """
    Открыть карточку товара (устаревший путь без контекста).
    Кнопка «Назад к товарам» будет вести в noop. Сохранено для совместимости.
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
    kb = build_product_card_kb(product_id=product.id, back_to=None)

    if product.images:
        img = product.images[0]
        if getattr(img, "telegram_file_id", None):
            await callback.message.answer_photo(photo=img.telegram_file_id, caption=caption, reply_markup=kb)
        elif getattr(img, "url", None):
            await callback.message.answer_photo(photo=img.url, caption=caption, reply_markup=kb)
        else:
            await callback.message.answer(caption, reply_markup=kb)
    else:
        await callback.message.answer(caption, reply_markup=kb)

    await callback.answer()


async def _build_products_keyboard(session: AsyncSession, *, category_id: int, page: int, page_size: int):
    """
    Собрать клавиатуру списка товаров с пагинацией.

    Параметры:
    - category_id: категория, товары которой показываем
    - page:       текущая страница (0..N)
    - page_size:  количество товаров на страницу

    Алгоритм:
    - Получаем товары для текущей страницы (limit/offset).
    - Проверяем наличие «следующей» страницы, запросив +1 элемент.
    - Возвращаем InlineKeyboardMarkup с кнопками товаров и навигацией.
    """
    offset = max(0, page) * page_size
    products = await list_products(session, category_id=category_id, limit=page_size, offset=offset)

    # Проверяем, есть ли следующая страница: запросим на один больше
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
