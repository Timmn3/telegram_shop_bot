"""
Клавиатуры админ-панели: меню, список заказов и статусы.
"""
from __future__ import annotations

from typing import Iterable
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from app.db.models import Order, OrderStatus


def build_admin_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню администратора."""
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить товар", callback_data="admin:cmd:add")
    kb.button(text="📦 Заказы", callback_data="admin:cmd:orders")
    kb.adjust(2)
    return kb.as_markup()


def build_orders_page_kb(*, orders: Iterable[Order], page: int, page_size: int, has_next: bool) -> InlineKeyboardMarkup:
    """
    Список заказов: на строку — номер и кнопка смены статуса (отдельным сообщением).
    Внизу — пагинация.
    """
    kb = InlineKeyboardBuilder()
    has_any = False
    for o in orders:
        has_any = True
        kb.button(text=f"{o.order_number} — {o.total_amount} {o.currency}", callback_data="noop")
        kb.button(text=f"Статус: {o.status.value}", callback_data=f"admin:order:status:{o.id}:{o.status.value}")
        kb.adjust(1, 1)
    if not has_any:
        kb.button(text="Заказов нет", callback_data="noop")
        kb.adjust(1)

    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="◀️", callback_data=f"admin:orders:page:{page-1}:{page_size}")
    nav.button(text=f"Стр. {page+1}", callback_data="noop")
    if has_next:
        nav.button(text="▶️", callback_data=f"admin:orders:page:{page+1}:{page_size}")

    kb = InlineKeyboardBuilder(markup=kb.as_markup())
    kb.attach(nav)
    return kb.as_markup()


def build_order_status_kb(*, order_id: int, current: OrderStatus) -> InlineKeyboardMarkup:
    """
    Кнопки для смены статуса заказа.
    """
    kb = InlineKeyboardBuilder()
    for status in OrderStatus:
        mark = "✅ " if status == current else ""
        kb.button(text=f"{mark}{status.value}", callback_data=f"admin:order:status:{order_id}:{status.value}")
    kb.adjust(2, 3)
    return kb.as_markup()
