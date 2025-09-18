"""
Оформление заказа (FSM) с навигацией «Назад» на каждом шаге.

"""
from __future__ import annotations

import re
from aiogram import Router, F
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


# ─────────────────────────── Старт / Отмена ─────────────────────────── #

@checkout_router.callback_query(F.data == "checkout:start")
async def checkout_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Старт оформления заказа:
    - Проверяем, что корзина не пуста
    - Переходим на шаг ввода имени
    """
    user_id = callback.from_user.id if callback.from_user else 0
    async with AsyncSessionFactory() as session:
        items = await cart_service.list_items(session, user_id=user_id)

    if not items:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    await state.clear()
    await state.set_state(CheckoutSG.name)
    await callback.message.answer("Введите ваше имя:", reply_markup=build_cancel_kb(include_back=True))
    await callback.answer()


@checkout_router.callback_query(F.data == "checkout:cancel")
async def checkout_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена оформления заказа (сброс FSM)."""
    await state.clear()
    await callback.message.answer("❌ Оформление заказа отменено.")
    await callback.answer()


# ─────────────────────────── Шаг 1: Имя ─────────────────────────── #

@checkout_router.message(CheckoutSG.name)
async def ask_phone(message: Message, state: FSMContext) -> None:
    """Получаем имя и просим телефон."""
    full_name = (message.text or "").strip()
    if not full_name:
        await message.answer(
            "Имя не должно быть пустым. Введите имя ещё раз:",
            reply_markup=build_cancel_kb(include_back=True),
        )
        return

    await state.update_data(contact_name=full_name)
    await state.set_state(CheckoutSG.phone)
    await message.answer(
        "Укажите телефон (например, +79991234567):",
        reply_markup=build_cancel_kb(include_back=True),
    )


# ─────────────────────────── Шаг 2: Телефон ─────────────────────────── #

@checkout_router.message(CheckoutSG.phone)
async def ask_address(message: Message, state: FSMContext) -> None:
    """Валидируем телефон и просим адрес."""
    phone = (message.text or "").strip()
    if not _is_phone(phone):
        await message.answer(
            "Телефон выглядит некорректно. Пример: +79991234567. Введите ещё раз:",
            reply_markup=build_cancel_kb(include_back=True),
        )
        return

    await state.update_data(contact_phone=phone)
    await state.set_state(CheckoutSG.address)
    await message.answer(
        "Введите адрес доставки (улица, дом, квартира) или '-' если самовывоз:",
        reply_markup=build_cancel_kb(include_back=True),
    )


# ─────────────────────────── Шаг 3: Адрес ─────────────────────────── #

@checkout_router.message(CheckoutSG.address)
async def ask_delivery(message: Message, state: FSMContext) -> None:
    """Получаем адрес и предлагаем выбрать способ доставки."""
    address = (message.text or "").strip()
    await state.update_data(address=None if address == "-" else address)
    await state.set_state(CheckoutSG.delivery)
    await message.answer("Выберите способ доставки:", reply_markup=build_delivery_kb(include_back=True))


# ─────────────────────────── Шаг 4: Доставка ─────────────────────────── #

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
    await callback.message.answer(preview, reply_markup=build_confirm_kb(include_back=True))
    await callback.answer()


# ─────────────────────────── Шаг 5: Подтверждение ─────────────────────────── #

@checkout_router.callback_query(CheckoutSG.confirm, F.data == "checkout:confirm")
async def checkout_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Создание заказа из корзины и уведомление админов."""
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
            text = (
                f"📦 Новый заказ {order.order_number}\n"
                f"Пользователь: {user_id}\n"
                f"Сумма: {order.total_amount} {order.currency}"
            )
            for admin_id in settings.ADMIN_ID_LIST:
                await callback.message.bot.send_message(chat_id=admin_id, text=text)
    except Exception:
        logger.exception("Ошибка уведомления админов о заказе %s", getattr(order, "id", None))


# ─────────────────────────── Back-навигация ─────────────────────────── #

@checkout_router.callback_query(F.data == "checkout:back")
async def checkout_back(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Универсальная кнопка «⬅️ Назад».
    Переходит на предыдущий шаг, подставляет сохранённые значения в подсказки.
    """
    current = await state.get_state()

    # name → отмена (равно cancel)
    if current == CheckoutSG.name.state:
        await checkout_cancel(callback, state)
        return

    # phone → name
    if current == CheckoutSG.phone.state:
        await state.set_state(CheckoutSG.name)
        data = await state.get_data()
        hint = f" (текущее: <code>{data.get('contact_name','')}</code>)" if data.get("contact_name") else ""
        await callback.message.answer(
            f"Измените имя{hint}:\nОтправьте новое значение.",
            reply_markup=build_cancel_kb(include_back=True),
        )
        await callback.answer()
        return

    # address → phone
    if current == CheckoutSG.address.state:
        await state.set_state(CheckoutSG.phone)
        data = await state.get_data()
        hint = f" (текущий: <code>{data.get('contact_phone','')}</code>)" if data.get("contact_phone") else ""
        await callback.message.answer(
            f"Измените телефон{hint}:\nПример: +79991234567",
            reply_markup=build_cancel_kb(include_back=True),
        )
        await callback.answer()
        return

    # delivery → address
    if current == CheckoutSG.delivery.state:
        await state.set_state(CheckoutSG.address)
        data = await state.get_data()
        addr = data.get("address")
        hint = f" (текущий: <code>{addr}</code>)" if addr else " (сейчас: самовывоз)"
        await callback.message.answer(
            f"Измените адрес доставки{hint}:\nИли отправьте '-' для самовывоза.",
            reply_markup=build_cancel_kb(include_back=True),
        )
        await callback.answer()
        return

    # confirm → delivery
    if current == CheckoutSG.confirm.state:
        await state.set_state(CheckoutSG.delivery)
        await callback.message.answer(
            "Выберите способ доставки:",
            reply_markup=build_delivery_kb(include_back=True),
        )
        await callback.answer()
        return

    # На случай неизвестного состояния — просто отмена
    await checkout_cancel(callback, state)


# ─────────────────────────── Валидация ─────────────────────────── #

def _is_phone(s: str) -> bool:
    """Простая валидация телефона: +? и 10–15 цифр."""
    return bool(re.fullmatch(r"\+?\d{10,15}", s or ""))
