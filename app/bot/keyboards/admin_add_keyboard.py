"""
Клавиатуры для FSM добавления товара админом: «⬅️ Назад» и «🚫 Отмена».

Использование:
    reply_markup=build_admin_cancel_kb(include_back=True/False)
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


BACK_CB = "admin:add:back"
CANCEL_CB = "admin:add:cancel"


def build_admin_cancel_kb(*, include_back: bool) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру управления шагами FSM.
    :param include_back: показывать ли кнопку «Назад» (на первом шаге её нет).
    """
    rows: list[list[InlineKeyboardButton]] = []

    if include_back:
        rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=BACK_CB)])

    rows.append([InlineKeyboardButton(text="🚫 Отмена", callback_data=CANCEL_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
