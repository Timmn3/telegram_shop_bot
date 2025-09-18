"""
Клавиатуры для FSM редактирования товара (админ).

"""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

EDIT_BACK_CB = "admin:edit:back"
EDIT_CANCEL_CB = "admin:edit:cancel"


def build_edit_menu_kb(*, product_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора поля для редактирования."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Название", callback_data=f"admin:edit:field:title:{product_id}")
    kb.button(text="💰 Цена", callback_data=f"admin:edit:field:price:{product_id}")
    kb.button(text="📁 Категория", callback_data=f"admin:edit:field:category:{product_id}")
    kb.button(text="📝 Описание", callback_data=f"admin:edit:field:description:{product_id}")
    kb.button(text="⚙️ Активность", callback_data=f"admin:edit:field:active:{product_id}")
    kb.button(text="🖼 Фото (заменить)", callback_data=f"admin:edit:field:photos:{product_id}")
    kb.adjust(2, 2, 2)
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=EDIT_BACK_CB))
    kb.row(InlineKeyboardButton(text="🚫 Отмена", callback_data=EDIT_CANCEL_CB))
    return kb.as_markup()


def build_edit_back_cancel_kb(*, include_back: bool) -> InlineKeyboardMarkup:
    """Универсальная клавиатура «Назад/Отмена» для шагов ввода."""
    rows: list[list[InlineKeyboardButton]] = []
    if include_back:
        rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=EDIT_BACK_CB)])
    rows.append([InlineKeyboardButton(text="🚫 Отмена", callback_data=EDIT_CANCEL_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
