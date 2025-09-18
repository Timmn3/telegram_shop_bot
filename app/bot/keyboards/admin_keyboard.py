"""
Клавиатуры админ-панели: меню, список заказов и статусы.
"""
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from app.db.models import Order, OrderStatus

def build_admin_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню администратора."""
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить товар", callback_data="admin:cmd:add")
    kb.button(text="📦 Заказы", callback_data="admin:cmd:orders")
    kb.adjust(2)
    return kb.as_markup()


def build_orders_page_kb(*, orders: list[Order], page: int, page_size: int, has_next: bool):
    """
    Клавиатура списка заказов.
    На каждый заказ — 2 кнопки:
      1) Открыть карточку: admin:order:open:<order_id>
      2) Показать статус (no-op): admin:noop
    Внизу — пагинация.
    """
    kb = InlineKeyboardBuilder()

    if not orders:
        kb.row(InlineKeyboardButton(text="Нет заказов", callback_data="admin:noop"))
    else:
        for o in orders:
            title = f"{o.order_number} — {o.total_amount} {o.currency}"
            kb.row(
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"admin:order:open:{o.id}",
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text=f"Статус: {o.status.value}",
                    callback_data="admin:noop",
                )
            )

    # пагинация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin:orders:page:{page-1}:{page_size}"))
    nav.append(InlineKeyboardButton(text=f"Стр. {page+1}", callback_data="admin:noop"))
    if has_next:
        nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"admin:orders:page:{page+1}:{page_size}"))
    kb.row(*nav)

    return kb.as_markup()



def build_order_status_kb(*, order_id: int, current: OrderStatus) -> InlineKeyboardMarkup:
    """Кнопки для смены статуса заказа."""
    kb = InlineKeyboardBuilder()
    for status in OrderStatus:
        mark = "✅ " if status == current else ""
        kb.button(text=f"{mark}{status.value}", callback_data=f"admin:order:status:{order_id}:{status.value}")
    kb.adjust(2, 3)
    return kb.as_markup()
