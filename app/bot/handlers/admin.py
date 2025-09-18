"""
Админ-панель: меню, список заказов и FSM добавления товара с «Назад/Отмена».

"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional, List

from aiogram import Router, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ContentType

from app.core.config import settings
from app.core.logging_cfg import logger
from app.db.session import AsyncSessionFactory
from app.db.models import Order, OrderStatus, ProductImage
from app.db.repository import OrderRepo, ProductRepo, CategoryRepo
from app.bot.keyboards.admin_keyboard import (
    build_admin_menu_kb,
    build_orders_page_kb,
    build_order_status_kb,
)
from app.bot.keyboards.admin_add_keyboard import build_admin_cancel_kb, BACK_CB, CANCEL_CB

admin_router = Router(name="admin")


# =======================
#  Фильтр «только админы»
# =======================
class AdminOnly(BaseFilter):
    """Пропускает только Telegram ID из settings.ADMIN_ID_LIST."""
    async def __call__(self, obj: Message | CallbackQuery) -> bool:
        uid: Optional[int] = None
        if isinstance(obj, Message):
            uid = obj.from_user.id if obj.from_user else None
        else:
            uid = obj.from_user.id if obj.from_user else None
        return bool(uid and uid in settings.ADMIN_ID_LIST)


# ==========
#  Меню /admin
# ==========
@admin_router.message(AdminOnly(), Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Показать главное меню администратора."""
    await message.answer("⚙️ Админ-панель:", reply_markup=build_admin_menu_kb())
    logger.debug("Админ %s открыл меню", message.from_user.id if message.from_user else None)


@admin_router.callback_query(AdminOnly(), F.data == "admin:cmd:add")
async def cb_admin_cmd_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка «Добавить товар» → запуск FSM."""
    await add_product_start(callback, state)


@admin_router.callback_query(AdminOnly(), F.data == "admin:cmd:orders")
async def cb_admin_cmd_orders(callback: CallbackQuery) -> None:
    """Кнопка «Заказы» → открываем список заказов."""
    await show_orders_page(callback, page=0, page_size=10)


# ============================
#  Список заказов и пагинация
# ============================
async def show_orders_page(cb_or_msg: CallbackQuery | Message, *, page: int, page_size: int) -> None:
    """Показать страницу заказов администратору."""
    offset = max(0, page) * page_size
    async with AsyncSessionFactory() as session:
        orders: List[Order] = await OrderRepo.list_for_admin(session, limit=page_size, offset=offset)
    kb = build_orders_page_kb(orders=orders, page=page, page_size=page_size, has_next=len(orders) == page_size)
    text = "📦 Заказы (последние):"
    if isinstance(cb_or_msg, CallbackQuery) and cb_or_msg.message:
        await cb_or_msg.message.edit_text(text, reply_markup=kb)
        await cb_or_msg.answer()
    else:
        await cb_or_msg.answer(text, reply_markup=kb)  # type: ignore


@admin_router.callback_query(AdminOnly(), F.data.startswith("admin:orders:page:"))
async def admin_orders_page(callback: CallbackQuery) -> None:
    """Пагинация заказов: admin:orders:page:<page>:<page_size>."""
    try:
        _, _, _, p, sz = callback.data.split(":")
        page = int(p)
        size = int(sz)
    except Exception:
        await callback.answer("Некорректная страница", show_alert=True)
        return
    await show_orders_page(callback, page=page, page_size=size)


@admin_router.callback_query(AdminOnly(), F.data.startswith("admin:order:status:"))
async def admin_order_set_status(callback: CallbackQuery) -> None:
    """Смена статуса заказа из окна карточки заказа."""
    try:
        _, _, _, oid, status_str = callback.data.split(":")
        order_id = int(oid)
        new_status = OrderStatus(status_str)
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    async with AsyncSessionFactory() as session:
        async with session.begin():
            order = await OrderRepo.get(session, order_id)
            if not order:
                await callback.answer("Заказ не найден", show_alert=True)
                return

            if order.status == new_status:
                kb_same = build_order_status_kb(order_id=order.id, current=order.status)
                if callback.message:
                    await callback.message.edit_reply_markup(reply_markup=kb_same)
                await callback.answer()
                return

            updated = await OrderRepo.set_status(session, order_id, new_status)

    if callback.message:
        text = (
            f"📦 Заказ <b>{updated.order_number}</b>\n"
            f"Статус: <b>{updated.status.value}</b>\n"
            f"Сумма: {updated.total_amount} {updated.currency}\n"
            f"Имя: {updated.contact_name}\n"
            f"Телефон: {updated.contact_phone}\n"
            f"Адрес: {updated.address or '—'}\n"
            f"Доставка: {updated.delivery_type or '—'}"
        )
        kb = build_order_status_kb(order_id=updated.id, current=updated.status)
        await callback.message.edit_text(text, reply_markup=kb)

    await callback.answer("Статус обновлён")


@admin_router.callback_query(AdminOnly(), F.data.startswith("admin:order:open:"))
async def admin_order_open(callback: CallbackQuery):
    """Открыть заказ отдельным сообщением с кнопками статуса."""
    try:
        order_id = int(callback.data.split(":")[3])
    except Exception:
        await callback.answer("Некорректный id", show_alert=True)
        return

    async with AsyncSessionFactory() as session:
        order = await OrderRepo.get(session, order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    text = (
        f"📦 Заказ <b>{order.order_number}</b>\n"
        f"Статус: <b>{order.status.value}</b>\n"
        f"Сумма: {order.total_amount} {order.currency}\n"
        f"Имя: {order.contact_name}\n"
        f"Телефон: {order.contact_phone}\n"
        f"Адрес: {order.address or '—'}\n"
        f"Доставка: {order.delivery_type or '—'}"
    )
    kb = build_order_status_kb(order_id=order.id, current=order.status)
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@admin_router.callback_query(AdminOnly(), F.data == "admin:noop")
async def admin_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ===========================
#  Добавление товара (FSM)
# ===========================
class AddProductSG(StatesGroup):
    """
    Состояния FSM добавления товара.

    Поток:
        title -> price -> category_id -> description -> photos(loop) -> active -> confirm
    """
    title = State()
    price = State()
    category_id = State()
    description = State()
    photos = State()   # <-- цикл добавления фото
    active = State()
    confirm = State()


# ─────────────── Старт/Отмена/Назад (универсальные) ─────────────── #

@admin_router.message(AdminOnly(), Command("admin_add_product"))
async def add_product_start_cmd(message: Message, state: FSMContext) -> None:
    """Запуск FSM добавления товара командой."""
    await state.clear()
    await state.set_state(AddProductSG.title)
    await message.answer("Введите название товара:", reply_markup=build_admin_cancel_kb(include_back=False))


@admin_router.callback_query(AdminOnly(), F.data == "admin:add_product")
async def add_product_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Запуск FSM добавления товара из инлайн-меню."""
    await state.clear()
    await state.set_state(AddProductSG.title)
    await callback.message.answer("Введите название товара:", reply_markup=build_admin_cancel_kb(include_back=False))
    await callback.answer()


@admin_router.callback_query(AdminOnly(), F.data == CANCEL_CB)
async def add_product_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Универсальная отмена FSM добавления товара."""
    await state.clear()
    await callback.message.answer("❌ Добавление товара отменено.")
    await callback.answer()


@admin_router.callback_query(AdminOnly(), F.data == BACK_CB)
async def add_product_back(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Универсальная «⬅️ Назад» для FSM добавления товара.
    Возвращает на предыдущий шаг и выводит подсказку с текущим значением.
    """
    current = await state.get_state()
    data = await state.get_data()

    # title → отмена
    if current == AddProductSG.title.state:
        await add_product_cancel(callback, state)
        return

    # price → title
    if current == AddProductSG.price.state:
        await state.set_state(AddProductSG.title)
        hint = f" (текущее: <code>{data.get('title','')}</code>)" if data.get("title") else ""
        await callback.message.answer(f"Измените название{hint}:", reply_markup=build_admin_cancel_kb(include_back=False))
        await callback.answer()
        return

    # category_id → price
    if current == AddProductSG.category_id.state:
        await state.set_state(AddProductSG.price)
        hint = f" (текущая: <code>{data.get('price','')}</code>)" if data.get("price") else ""
        await callback.message.answer(
            f"Измените цену{hint} (пример: 1999.99):",
            reply_markup=build_admin_cancel_kb(include_back=True),
        )
        await callback.answer()
        return

    # description → category_id
    if current == AddProductSG.description.state:
        await state.set_state(AddProductSG.category_id)
        await _prompt_categories(callback.message, include_back=True)
        await callback.answer()
        return

    # photos → description
    if current == AddProductSG.photos.state:
        await state.set_state(AddProductSG.description)
        desc = data.get("description")
        hint = f" (текущее: <code>{desc}</code>)" if desc else " (сейчас: пусто)"
        await callback.message.answer(
            f"Измените описание{hint} (или '-' чтобы пропустить):",
            reply_markup=build_admin_cancel_kb(include_back=True),
        )
        await callback.answer()
        return

    # active → photos
    if current == AddProductSG.active.state:
        await state.set_state(AddProductSG.photos)
        count = len(data.get("_photos", []))
        await callback.message.answer(
            f"Пришлите фото товара (принято: {count}). «готово» — завершить, '-' — пропустить.",
            reply_markup=build_admin_cancel_kb(include_back=True),
        )
        await callback.answer()
        return

    # confirm → active
    if current == AddProductSG.confirm.state:
        await state.set_state(AddProductSG.active)
        is_active = data.get("is_active")
        hint = f" (сейчас: {'Да' if is_active else 'Нет'})"
        await callback.message.answer(
            f"Активировать товар? Введите «да/нет»{hint}:",
            reply_markup=build_admin_cancel_kb(include_back=True),
        )
        await callback.answer()
        return

    # По умолчанию — отменяем
    await add_product_cancel(callback, state)


# ─────────────── Шаги FSM (с клавиатурами Назад/Отмена) ─────────────── #

@admin_router.message(AdminOnly(), AddProductSG.title)
async def add_product_title(message: Message, state: FSMContext) -> None:
    """Шаг: название товара."""
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не должно быть пустым. Введите ещё раз:",
                             reply_markup=build_admin_cancel_kb(include_back=False))
        return
    await state.update_data(title=title)
    await state.set_state(AddProductSG.price)
    await message.answer("Введите цену (пример: 1999.99):",
                         reply_markup=build_admin_cancel_kb(include_back=True))


@admin_router.message(AdminOnly(), AddProductSG.price)
async def add_product_price(message: Message, state: FSMContext) -> None:
    """Шаг: цена товара (Decimal, > 0)."""
    raw = (message.text or "").replace(",", ".").strip()
    try:
        price = Decimal(raw)
        if price <= 0:
            raise InvalidOperation
    except Exception:
        await message.answer("Цена некорректна. Пример: 1999.99 — попробуйте ещё раз:",
                             reply_markup=build_admin_cancel_kb(include_back=True))
        return
    await state.update_data(price=str(price))
    await state.set_state(AddProductSG.category_id)
    await _prompt_categories(message, include_back=True)


async def _prompt_categories(msg_or_cbmsg: Message, *, include_back: bool) -> None:
    """Вспомогательная функция для показа списка корневых категорий и запроса ID."""
    async with AsyncSessionFactory() as session:
        roots = await CategoryRepo.list_root(session)
    if roots:
        cats_text = "\n".join(f"{c.id}: {c.title}" for c in roots)
        await msg_or_cbmsg.answer(
            f"Введите ID категории из списка:\n{cats_text}\n(или 0 — без категории)",
            reply_markup=build_admin_cancel_kb(include_back=include_back),
        )
    else:
        await msg_or_cbmsg.answer(
            "Категорий пока нет. Введите 0 для сохранения без категории.",
            reply_markup=build_admin_cancel_kb(include_back=include_back),
        )


@admin_router.message(AdminOnly(), AddProductSG.category_id)
async def add_product_category(message: Message, state: FSMContext) -> None:
    """Шаг: категория ID (целое число; 0 — без категории)."""
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("ID категории должен быть числом. Повторите ввод:",
                             reply_markup=build_admin_cancel_kb(include_back=True))
        return
    cid = int(raw)
    if cid != 0:
        async with AsyncSessionFactory() as session:
            if not await CategoryRepo.get(session, cid):
                await message.answer("Категория не найдена. Введите другой ID или 0:",
                                     reply_markup=build_admin_cancel_kb(include_back=True))
                return
    await state.update_data(category_id=None if cid == 0 else cid)
    await state.set_state(AddProductSG.description)
    await message.answer("Введите описание (или '-' чтобы пропустить):",
                         reply_markup=build_admin_cancel_kb(include_back=True))


@admin_router.message(AdminOnly(), AddProductSG.description)
async def add_product_description(message: Message, state: FSMContext) -> None:
    """Шаг: описание (или '-' — пропустить). После — цикл фото."""
    desc = None if (message.text or "").strip() == "-" else (message.text or "").strip()
    await state.update_data(description=desc)
    await state.set_state(AddProductSG.photos)
    await state.update_data(_photos=[])  # временный буфер фото (telegram_file_id)
    await message.answer(
        "Пришлите фото товара (можно несколько подряд). Когда закончите — отправьте <b>«готово»</b>.\n"
        "Или отправьте '-' чтобы пропустить добавление фото.",
        reply_markup=build_admin_cancel_kb(include_back=True),
    )


@admin_router.message(AdminOnly(), AddProductSG.photos, F.text)
async def add_product_photos_text_control(message: Message, state: FSMContext) -> None:
    """
    Управляющие ответы на шаге фото:
    - 'готово' → переходим к active
    - '-' → пропускаем фото, переходим к active
    - любое другое текстовое — подсказка
    """
    txt = (message.text or "").strip().lower()
    if txt in {"готово", "done", "end", "finish"} or txt == "-":
        await state.set_state(AddProductSG.active)
        photos = (await state.get_data()).get("_photos", [])
        if photos:
            await message.answer(
                f"Фото добавлены: {len(photos)} шт.\nАктивировать товар? (да/нет):",
                reply_markup=build_admin_cancel_kb(include_back=True),
            )
        else:
            await message.answer(
                "Фото пропущены.\nАктивировать товар? (да/нет):",
                reply_markup=build_admin_cancel_kb(include_back=True),
            )
        return

    await message.answer(
        "Пришлите фото, либо «готово» для завершения, либо '-' чтобы пропустить.",
        reply_markup=build_admin_cancel_kb(include_back=True),
    )


@admin_router.message(AdminOnly(), AddProductSG.photos, F.content_type == ContentType.PHOTO)
async def add_product_photos_collect(message: Message, state: FSMContext) -> None:
    """
    Принимаем фото и складываем их file_id во временный список в FSM.
    Порядок сохранения соответствует sort_order.
    """
    if not message.photo:
        await message.answer("Не удалось получить фото. Пришлите изображение ещё раз.",
                             reply_markup=build_admin_cancel_kb(include_back=True))
        return

    file_id = message.photo[-1].file_id
    data = await state.get_data()
    photos: List[str] = list(data.get("_photos", []))
    photos.append(file_id)
    await state.update_data(_photos=photos)
    await message.answer(
        f"Фото принято ✅ (всего: {len(photos)}). Пришлите ещё или «готово».",
        reply_markup=build_admin_cancel_kb(include_back=True),
    )


@admin_router.message(AdminOnly(), AddProductSG.active)
async def add_product_active(message: Message, state: FSMContext) -> None:
    """Шаг: активность (да/нет)."""
    txt = (message.text or "").strip().lower()
    is_active = txt in {"да", "yes", "y", "true", "1", "ага", "включить"}
    await state.update_data(is_active=is_active)

    data = await state.get_data()
    photo_count = len(data.get("_photos", []))
    preview = (
        "<b>Подтверждение:</b>\n"
        f"Название: <b>{data['title']}</b>\n"
        f"Цена: <b>{data['price']}</b>\n"
        f"Категория ID: <b>{data.get('category_id') or '—'}</b>\n"
        f"Описание: <i>{data.get('description') or '—'}</i>\n"
        f"Фото: <b>{photo_count}</b> шт.\n"
        f"Активен: <b>{'Да' if data['is_active'] else 'Нет'}</b>\n\n"
        "Отправьте «да» для подтверждения или «нет» для отмены."
    )
    await state.set_state(AddProductSG.confirm)
    await message.answer(preview, reply_markup=build_admin_cancel_kb(include_back=True))


@admin_router.message(AdminOnly(), AddProductSG.confirm)
async def add_product_confirm(message: Message, state: FSMContext) -> None:
    """Финальное подтверждение: создаём Product и ProductImage*."""
    ok = (message.text or "").strip().lower() in {"да", "yes", "y"}
    if not ok:
        await state.clear()
        await message.answer("Создание товара отменено.")
        return

    data = await state.get_data()
    photos: List[str] = list(data.get("_photos", []))

    async with AsyncSessionFactory() as session:
        await session.begin()
        product = await ProductRepo.create(
            session,
            title=data["title"],
            price=Decimal(data["price"]),
            currency="EUR",
            category_id=data.get("category_id"),
            description=data.get("description"),
            is_active=bool(data.get("is_active", True)),
        )
        # Сохранить фото в ProductImage с sort_order
        for idx, file_id in enumerate(photos):
            session.add(ProductImage(product_id=product.id, telegram_file_id=file_id, sort_order=idx))
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Товар создан: <b>{product.title}</b>\nФото: {len(photos)} шт.")
