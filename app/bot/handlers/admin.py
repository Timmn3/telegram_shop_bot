"""
Админ-панель внутри бота.

Команды:
- /admin — меню администратора
- /admin_add_product — пошаговое добавление товара (FSM)
- /admin_orders — список заказов с кнопками смены статуса
- /admin_product_toggle <product_id> — переключить активность товара (вкл/выкл)

Доступ ограничен: только ID из settings.ADMIN_ID_LIST.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.core.config import settings
from app.core.logging_cfg import logger
from app.db.session import AsyncSessionFactory
from app.db.repository import ProductRepo, CategoryRepo
from app.db.models import OrderStatus
from app.services.order_service import list_orders_for_admin, set_order_status
from app.bot.keyboards.admin_keyboard import (
    build_admin_menu_kb,
    build_orders_page_kb,
    build_order_status_kb,
)

admin_router = Router(name="admin")


# ------------ Доступ только для админов ------------
class AdminOnly(BaseFilter):
    """Фильтр: пропускает только пользователей из ADMIN_ID_LIST."""
    async def __call__(self, message: Message | CallbackQuery) -> bool:
        uid: Optional[int] = None
        if isinstance(message, Message):
            uid = message.from_user.id if message.from_user else None
        else:
            uid = message.from_user.id if message.from_user else None
        return bool(uid and uid in settings.ADMIN_ID_LIST)


# ------------ Меню администратора ------------
@admin_router.message(AdminOnly(), Command("admin"))
async def admin_menu(message: Message) -> None:
    """Показывает клавиатуру меню админа."""
    await message.answer("🛠 Меню администратора:", reply_markup=build_admin_menu_kb())


# ------------ Добавление товара (FSM) ------------
class AddProductSG(StatesGroup):
    title = State()
    price = State()
    category_id = State()
    description = State()
    confirm = State()


@admin_router.message(AdminOnly(), Command("admin_add_product"))
async def admin_add_product_start(message: Message, state: FSMContext) -> None:
    """Старт добавления товара."""
    await state.clear()
    await state.set_state(AddProductSG.title)
    await message.answer("Введите название товара:")


@admin_router.message(AdminOnly(), AddProductSG.title)
async def add_product_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не должно быть пустым. Повторите:")
        return
    await state.update_data(title=title)
    await state.set_state(AddProductSG.price)
    await message.answer("Введите цену (например, 1999.90):")


@admin_router.message(AdminOnly(), AddProductSG.price)
async def add_product_price(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").replace(",", ".").strip()
    try:
        price = Decimal(raw)
        if price <= 0:
            raise ValueError
    except Exception:
        await message.answer("Некорректная цена. Введите ещё раз (пример 1999.90):")
        return

    await state.update_data(price=str(price))
    await state.set_state(AddProductSG.category_id)
    await message.answer("Введите ID категории (число). Если без категории — отправьте 0:")


@admin_router.message(AdminOnly(), AddProductSG.category_id)
async def add_product_category(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Ожидалось число. Введите ID категории или 0:")
        return
    cat_id = int(raw)
    # необязательная валидация существования категории
    if cat_id != 0:
        async with AsyncSessionFactory() as session:
            cat = await CategoryRepo.get(session, cat_id)
            if not cat:
                await message.answer("Категория не найдена. Введите другой ID или 0:")
                return

    await state.update_data(category_id=cat_id if cat_id != 0 else None)
    await state.set_state(AddProductSG.description)
    await message.answer("Введите описание (или '-' чтобы оставить пустым):")


@admin_router.message(AdminOnly(), AddProductSG.description)
async def add_product_description(message: Message, state: FSMContext) -> None:
    desc = None if (message.text or "").strip() == "-" else (message.text or "").strip()
    await state.update_data(description=desc)
    data = await state.get_data()

    preview = (
        "<b>Подтверждение создания товара:</b>\n\n"
        f"Название: <b>{data['title']}</b>\n"
        f"Цена: <b>{data['price']}</b>\n"
        f"Категория ID: <b>{data.get('category_id') or '—'}</b>\n"
        f"Описание: <i>{data.get('description') or '—'}</i>\n\n"
        "Отправьте «да» для подтверждения или «нет» для отмены."
    )
    await state.set_state(AddProductSG.confirm)
    await message.answer(preview)


@admin_router.message(AdminOnly(), AddProductSG.confirm)
async def add_product_confirm(message: Message, state: FSMContext) -> None:
    answer = (message.text or "").strip().lower()
    if answer not in {"да", "yes", "y"}:
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
            is_active=True,
        )
    await state.clear()
    await message.answer(f"✅ Товар создан: <b>{product.title}</b> (id={product.id})")


# ------------ Тоггл активности товара ------------
@admin_router.message(AdminOnly(), Command("admin_product_toggle"))
async def admin_product_toggle(message: Message) -> None:
    """
    Переключить активность товара: /admin_product_toggle <product_id>
    """
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /admin_product_toggle <product_id>")
        return
    product_id = int(parts[1])

    async with AsyncSessionFactory() as session:
        product = await ProductRepo.get(session, product_id)
        if not product:
            await message.answer("Товар не найден.")
            return
        new_state = not bool(product.is_active)
        product = await ProductRepo.update(session, product_id, is_active=new_state)

    await message.answer(f"Статус товара #{product_id}: {'АКТИВЕН' if product.is_active else 'ОТКЛЮЧЕН'}")


# ------------ Просмотр заказов и смена статуса ------------
@admin_router.message(AdminOnly(), Command("admin_orders"))
async def admin_orders(message: Message) -> None:
    """Показывает первую страницу заказов."""
    page, page_size = 0, 10
    async with AsyncSessionFactory() as session:
        orders = await list_orders_for_admin(session, limit=page_size, offset=page * page_size)
    kb = build_orders_page_kb(orders=orders, page=page, page_size=page_size, has_next=len(orders) == page_size)
    await message.answer("📦 Заказы (последние):", reply_markup=kb)


@admin_router.callback_query(AdminOnly(), F.data.startswith("admin:orders:page:"))
async def admin_orders_page(callback: CallbackQuery) -> None:
    """Пагинация списка заказов."""
    _, _, _, p, sz = callback.data.split(":")
    page = max(0, int(p))
    page_size = int(sz)

    async with AsyncSessionFactory() as session:
        orders = await list_orders_for_admin(session, limit=page_size, offset=page * page_size)

    kb = build_orders_page_kb(orders=orders, page=page, page_size=page_size, has_next=len(orders) == page_size)
    await callback.message.edit_text("📦 Заказы (последние):", reply_markup=kb)
    await callback.answer()


@admin_router.callback_query(AdminOnly(), F.data.startswith("admin:order:status:"))
async def admin_order_set_status(callback: CallbackQuery) -> None:
    """
    Смена статуса заказа:
    callback: admin:order:status:<order_id>:<status>
    """
    try:
        _, _, _, oid, status_str = callback.data.split(":")
        order_id = int(oid)
        status = OrderStatus(status_str)
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    async with AsyncSessionFactory() as session:
        updated = await set_order_status(session, order_id=order_id, status=status)
    if not updated:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await callback.answer("Статус обновлён")
    # Обновим строку с кнопками статуса (простым сообщением)
    kb = build_order_status_kb(order_id=updated.id, current=updated.status)
    await callback.message.answer(f"Заказ {updated.order_number}: статус → <b>{updated.status.value}</b>", reply_markup=kb)
