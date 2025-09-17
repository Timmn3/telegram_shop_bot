"""
Админ-панель внутри бота.

Возможности:
- /admin — меню админа
- Добавление товара (FSM)
- Список заказов с пагинацией
- Смена статуса заказа
- Переключение активности товара (команда)

Доступ ограничен по settings.ADMIN_ID_LIST.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional, List

from aiogram import Router, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.core.config import settings
from app.core.logging_cfg import logger
from app.db.session import AsyncSessionFactory
from app.db.models import Order, OrderStatus
from app.db.repository import OrderRepo, ProductRepo, CategoryRepo
from app.bot.keyboards.admin_keyboard import (
    build_admin_menu_kb,
    build_orders_page_kb,
    build_order_status_kb,
)

admin_router = Router(name="admin")


# -------- фильтр доступа --------
class AdminOnly(BaseFilter):
    """Пускает только пользователей из ADMIN_ID_LIST."""
    async def __call__(self, obj: Message | CallbackQuery) -> bool:
        uid: Optional[int] = None
        if isinstance(obj, Message):
            uid = obj.from_user.id if obj.from_user else None
        else:
            uid = obj.from_user.id if obj.from_user else None
        return bool(uid and uid in settings.ADMIN_ID_LIST)


# -------- меню --------
@admin_router.message(AdminOnly(), Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer("⚙️ Админ-панель:", reply_markup=build_admin_menu_kb())
    logger.debug("Админ %s открыл меню", message.from_user.id if message.from_user else None)


# клики по кнопкам меню
@admin_router.callback_query(AdminOnly(), F.data == "admin:cmd:add")
async def cb_admin_cmd_add(callback: CallbackQuery, state: FSMContext) -> None:
    await add_product_start(callback, state)


@admin_router.callback_query(AdminOnly(), F.data == "admin:cmd:orders")
async def cb_admin_cmd_orders(callback: CallbackQuery) -> None:
    await show_orders_page(callback, page=0, page_size=10)


# -------- список заказов с пагинацией --------
async def show_orders_page(cb_or_msg: CallbackQuery | Message, *, page: int, page_size: int) -> None:
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
    """callback: admin:order:status:<order_id>:<status>"""
    try:
        _, _, _, oid, status_str = callback.data.split(":")
        order_id = int(oid)
        status = OrderStatus(status_str)
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    async with AsyncSessionFactory() as session:
        updated = await OrderRepo.set_status(session, order_id, status)
    if not updated:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    kb = build_order_status_kb(order_id=updated.id, current=updated.status)
    await callback.message.answer(
        f"Заказ {updated.order_number}: статус → <b>{updated.status.value}</b>",
        reply_markup=kb,
    )
    await callback.answer("Статус обновлён")


# -------- добавление товара (FSM) --------
class AddProductSG(StatesGroup):
    title = State()
    price = State()
    category_id = State()
    description = State()
    active = State()
    confirm = State()


@admin_router.callback_query(AdminOnly(), F.data == "admin:add_product")
async def add_product_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddProductSG.title)
    await callback.message.answer("Введите название товара:")
    await callback.answer()


@admin_router.message(AdminOnly(), Command("admin_add_product"))
async def add_product_start_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddProductSG.title)
    await message.answer("Введите название товара:")


@admin_router.message(AdminOnly(), AddProductSG.title)
async def add_product_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не должно быть пустым. Введите ещё раз:")
        return
    await state.update_data(title=title)
    await state.set_state(AddProductSG.price)
    await message.answer("Введите цену (пример: 1999.99):")


@admin_router.message(AdminOnly(), AddProductSG.price)
async def add_product_price(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").replace(",", ".").strip()
    try:
        price = Decimal(raw)
        if price <= 0:
            raise InvalidOperation
    except Exception:
        await message.answer("Цена некорректна. Пример: 1999.99 — попробуйте ещё раз:")
        return
    await state.update_data(price=str(price))
    await state.set_state(AddProductSG.category_id)

    async with AsyncSessionFactory() as session:
        roots = await CategoryRepo.list_root(session)
    if roots:
        cats_text = "\n".join(f"{c.id}: {c.title}" for c in roots)
        await message.answer(f"Введите ID категории из списка:\n{cats_text}\n(или 0 — без категории)")
    else:
        await message.answer("Категорий пока нет. Введите 0 для сохранения без категории.")


@admin_router.message(AdminOnly(), AddProductSG.category_id)
async def add_product_category(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("ID категории должен быть числом. Повторите ввод:")
        return
    cid = int(raw)
    if cid != 0:
        async with AsyncSessionFactory() as session:
            if not await CategoryRepo.get(session, cid):
                await message.answer("Категория не найдена. Введите другой ID или 0:")
                return
    await state.update_data(category_id=None if cid == 0 else cid)
    await state.set_state(AddProductSG.description)
    await message.answer("Введите описание (или '-' чтобы пропустить):")


@admin_router.message(AdminOnly(), AddProductSG.description)
async def add_product_description(message: Message, state: FSMContext) -> None:
    desc = None if (message.text or "").strip() == "-" else (message.text or "").strip()
    await state.update_data(description=desc)
    await state.set_state(AddProductSG.active)
    await message.answer("Активировать товар? (да/нет):")


@admin_router.message(AdminOnly(), AddProductSG.active)
async def add_product_active(message: Message, state: FSMContext) -> None:
    txt = (message.text or "").strip().lower()
    is_active = txt in {"да", "yes", "y", "true", "1", "ага", "включить"}
    await state.update_data(is_active=is_active)

    data = await state.get_data()
    preview = (
        "<b>Подтверждение:</b>\n"
        f"Название: <b>{data['title']}</b>\n"
        f"Цена: <b>{data['price']}</b>\n"
        f"Категория ID: <b>{data.get('category_id') or '—'}</b>\n"
        f"Описание: <i>{data.get('description') or '—'}</i>\n"
        f"Активен: <b>{'Да' if data['is_active'] else 'Нет'}</b>\n\n"
        "Отправьте «да» для подтверждения или «нет» для отмены."
    )
    await state.set_state(AddProductSG.confirm)
    await message.answer(preview)


@admin_router.message(AdminOnly(), AddProductSG.confirm)
async def add_product_confirm(message: Message, state: FSMContext) -> None:
    ok = (message.text or "").strip().lower() in {"да", "yes", "y"}
    if not ok:
        await state.clear()
        await message.answer("Создание товара отменено.")
        return

    data = await state.get_data()
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
    await state.clear()
    await message.answer(f"✅ Товар создан: <b>{product.title}</b>")
