from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def user_main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Кто сейчас онлайн", callback_data="menu:online")
    kb.button(text="Моя статистика", callback_data="menu:mystats:week")
    kb.button(text="Топ сегодня", callback_data="menu:top:day")
    kb.button(text="Избранное", callback_data="menu:favs")
    kb.button(text="Помощь", callback_data="menu:help")
    kb.adjust(1)
    return kb.as_markup()


def confirm_keyboard(action: str, payload: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=f"confirm:{action}:{payload}")
    kb.button(text="❌ Отмена", callback_data="confirm:cancel")
    kb.adjust(2)
    return kb.as_markup()
