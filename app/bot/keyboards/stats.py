from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def period_keyboard(prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="День", callback_data=f"{prefix}:day")
    kb.button(text="Неделя", callback_data=f"{prefix}:week")
    kb.button(text="Месяц", callback_data=f"{prefix}:month")
    kb.button(text="Всё", callback_data=f"{prefix}:all")
    kb.adjust(2, 2)
    return kb.as_markup()
