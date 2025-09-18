"""
Хэндлеры корзины

"""
from __future__ import annotations

from decimal import Decimal
from typing import List

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.core.logging_cfg import logger
from app.db.models import CartItem
from app.db.session import AsyncSessionFactory
from app.services import cart_service
from app.bot.keyboards.cart_keyboard import build_cart_keyboard, render_cart_text

cart_router = Router(name="cart")


# ====== Утилиты ======

async def _show_cart(message: Message | None, callback: CallbackQuery | None, user_id: int) -> None:
    """Общий метод показать корзину (отправляет/редактирует сообщение)."""
    async with AsyncSessionFactory() as session:
        items: List[CartItem] = await cart_service.list_items(session, user_id=user_id)
        total: Decimal = await cart_service.subtotal(session, user_id=user_id)

    text = render_cart_text(items, total)
    kb = build_cart_keyboard(items)

    # Если есть callback с сообщением — редактируем его, иначе отправляем новое
    if callback and callback.message:
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
    elif message:
        await message.answer(text, reply_markup=kb)
    else:
        logger.warning("Ни message, ни callback для отображения корзины")


# ====== Команды / Колбэки ======

@cart_router.message(Command("cart"))
async def cmd_cart(message: Message) -> None:
    """Команда /cart — показать содержимое корзины пользователя."""
    user_id = message.from_user.id if message.from_user else 0
    await _show_cart(message=message, callback=None, user_id=user_id)


@cart_router.callback_query(F.data == "cart:view")
async def cb_cart_view(callback: CallbackQuery) -> None:
    """Показать корзину по callback."""
    user_id = callback.from_user.id if callback.from_user else 0
    await _show_cart(message=None, callback=callback, user_id=user_id)


@cart_router.callback_query(F.data.startswith("cart:add:"))
async def cb_cart_add(callback: CallbackQuery) -> None:
    """
    Добавить товар в корзину.
    Ожидаемый формат callback.data: "cart:add:<product_id>"
    """
    user_id = callback.from_user.id if callback.from_user else 0
    try:
        product_id = int(callback.data.split(":")[2])
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    async with AsyncSessionFactory() as session:
        try:
            await cart_service.add_item(session, user_id=user_id, product_id=product_id, quantity=1)
        except ValueError as e:
            await callback.answer(str(e), show_alert=True)
            return

    await callback.answer("Добавлено в корзину ✅", show_alert=False)


@cart_router.callback_query(F.data.startswith("cart:inc:"))
async def cb_cart_inc(callback: CallbackQuery) -> None:
    """Увеличить количество позиции на 1."""
    user_id = callback.from_user.id if callback.from_user else 0
    try:
        product_id = int(callback.data.split(":")[2])
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    async with AsyncSessionFactory() as session:
        # Получим текущие позиции, чтобы понять текущее количество
        items = await cart_service.list_items(session, user_id=user_id)
        current_qty = next((i.quantity for i in items if i.product_id == product_id), 0)
        new_qty = max(0, current_qty + 1)
        await cart_service.set_quantity(session, user_id=user_id, product_id=product_id, quantity=new_qty)

    await _show_cart(message=None, callback=callback, user_id=user_id)


@cart_router.callback_query(F.data.startswith("cart:dec:"))
async def cb_cart_dec(callback: CallbackQuery) -> None:
    """Уменьшить количество позиции на 1 (если станет 0 — удаляем)."""
    user_id = callback.from_user.id if callback.from_user else 0
    try:
        product_id = int(callback.data.split(":")[2])
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    async with AsyncSessionFactory() as session:
        items = await cart_service.list_items(session, user_id=user_id)
        current_qty = next((i.quantity for i in items if i.product_id == product_id), 0)
        new_qty = max(0, current_qty - 1)
        await cart_service.set_quantity(session, user_id=user_id, product_id=product_id, quantity=new_qty)

    await _show_cart(message=None, callback=callback, user_id=user_id)


@cart_router.callback_query(F.data.startswith("cart:del:"))
async def cb_cart_del(callback: CallbackQuery) -> None:
    """Удалить позицию из корзины целиком."""
    user_id = callback.from_user.id if callback.from_user else 0
    try:
        product_id = int(callback.data.split(":")[2])
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    async with AsyncSessionFactory() as session:
        await cart_service.remove_item(session, user_id=user_id, product_id=product_id)

    await _show_cart(message=None, callback=callback, user_id=user_id)


@cart_router.callback_query(F.data == "cart:clear")
async def cb_cart_clear(callback: CallbackQuery) -> None:
    """Очистить корзину."""
    user_id = callback.from_user.id if callback.from_user else 0
    async with AsyncSessionFactory() as session:
        await cart_service.clear_cart(session, user_id=user_id)
    await _show_cart(message=None, callback=callback, user_id=user_id)


@cart_router.callback_query(F.data == "checkout:start")
async def cb_checkout_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Старт оформления заказа (делегируем в checkout.py).
    """
    from app.bot.handlers.checkout import checkout_start  # импортируем функцию-старт из checkout.py
    await checkout_start(callback, state)
