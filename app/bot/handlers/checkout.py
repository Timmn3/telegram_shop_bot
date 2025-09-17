"""
Оформление заказа (FSM):
- Старт из корзины по callback "checkout:start"
- Сбор данных: имя → телефон → адрес → способ доставки
- Подтверждение и создание заказа
"""
from __future__ import annotations

import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.core.config import settings
from app.core.logging_cfg import logger
from app.db.session import AsyncSessionFactory
from app.services import cart_service, order_service
from app.bot.keyboards.checkout_keyboard import (
    build_cancel_kb,
    build_delivery_kb,
    build_confirm_kb,
    render_order_preview,
)

checkout_router = Router(name="checkout")


class CheckoutSG(StatesGroup):
    """Состояния оформления заказа."""
    name = State()
    phone = State()
    address = State()
    delivery = State()
    confirm = State()


@checkout_router.callback_query(F.data == "checkout:start")
async def checkout_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Старт оформления заказа:
    - Проверяем, что корзина не пуста
    - Просим имя
    """
    user_id = callback.from_user.id if callback.from_user else 0
    async with AsyncSessionFactory() as session:
        total = await cart_service.subtotal(session, user_id=user_id)
        items = await cart_service.list_items(session, user_id=user_id)

    if not items:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    await state.clear()
    await state.set_state(CheckoutSG.name)
    await callback.message.answer("Введите ваше имя:", reply_markup=build_cancel_kb())
    await callback.answer()


@checkout_router.message(CheckoutSG.name)
async def ask_phone(message: Message, state: FSMContext) -> None:
    """Получаем имя и просим телефон."""
    full_name = (message.text or "").strip()
    if not full_name:
        await message.answer("Имя не должно быть пустым. Введите имя ещё раз:", reply_markup=build_cancel_kb())
        return

    await state.update_data(contact_name=full_name)
    await state.set_state(CheckoutSG.phone)
    await message.answer("Укажите телефон (например, +79991234567):", reply_markup=build_cancel_kb())


@checkout_router.message(CheckoutSG.phone)
async def ask_address(message: Message, state: FSMContext) -> None:
    """Валидируем телефон и просим адрес."""
    phone = (message.text or "").strip()
    if not _is_phone(phone):
        await message.answer("Телефон выглядит некорректно. Пример: +79991234567. Введите ещё раз:", reply_markup=build_cancel_kb())
        return

    await state.update_data(contact_phone=phone)
    await state.set_state(CheckoutSG.address)
    await message.answer("Введите адрес доставки (улица, дом, квартира) или '-' если самовывоз:", reply_markup=build_cancel_kb())


@checkout_router.message(CheckoutSG.address)
async def ask_delivery(message: Message, state: FSMContext) -> None:
    """Получаем адрес и предлагаем выбрать способ доставки."""
    address = (message.text or "").strip()
    await state.update_data(address=None if address == "-" else address)
    await state.set_state(CheckoutSG.delivery)
    await message.answer("Выберите способ доставки:", reply_markup=build_delivery_kb())


@checkout_router.callback_query(CheckoutSG.delivery, F.data.startswith("delivery:"))
async def confirm_screen(callback: CallbackQuery, state: FSMContext) -> None:
    """Фиксируем тип доставки и показываем экран подтверждения."""
    delivery_type = callback.data.split(":", 1)[1]
    await state.update_data(delivery_type=delivery_type)

    user_id = callback.from_user.id if callback.from_user else 0
    async with AsyncSessionFactory() as session:
        total = await cart_service.subtotal(session, user_id=user_id)
        items = await cart_service.list_items(session, user_id=user_id)

    data = await state.get_data()
    preview = render_order_preview(
        items=items,
        total=total,
        contact_name=data.get("contact_name", ""),
        contact_phone=data.get("contact_phone", ""),
        address=data.get("address"),
        delivery_type=delivery_type,
    )

    await state.set_state(CheckoutSG.confirm)
    await callback.message.answer(preview, reply_markup=build_confirm_kb())
    await callback.answer()


@checkout_router.callback_query(CheckoutSG.confirm, F.data == "checkout:confirm")
async def checkout_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Создание заказа из корзины и уведомление админа."""
    user_id = callback.from_user.id if callback.from_user else 0
    data = await state.get_data()

    try:
        async with AsyncSessionFactory() as session:
            order = await order_service.create_order_from_cart(
                session,
                user_id=user_id,
                contact_name=data["contact_name"],
                contact_phone=data["contact_phone"],
                address=data.get("address"),
                delivery_type=data.get("delivery_type"),
                currency="EUR",
            )
        await state.clear()
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    except Exception:
        logger.exception("Ошибка создания заказа для пользователя %s", user_id)
        await callback.answer("Не удалось создать заказ. Попробуйте позже.", show_alert=True)
        return

    await callback.message.answer(f"✅ Заказ оформлен!\nНомер: <b>{order.order_number}</b>")
    await callback.answer()

    # Уведомление админов
    try:
        if settings.ADMIN_ID_LIST:
            text = f"📦 Новый заказ {order.order_number}\nПользователь: {user_id}\nСумма: {order.total_amount} {order.currency}"
            for admin_id in settings.ADMIN_ID_LIST:
                await callback.message.bot.send_message(chat_id=admin_id, text=text)
    except Exception:
        logger.exception("Ошибка уведомления админов о заказе %s", order.id)


@checkout_router.callback_query(F.data == "checkout:cancel")
async def checkout_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена оформления заказа."""
    await state.clear()
    await callback.message.answer("❌ Оформление заказа отменено.")
    await callback.answer()


def _is_phone(s: str) -> bool:
    """Простая валидация телефона."""
    return bool(re.fullmatch(r"\+?\d{10,15}", s or ""))
