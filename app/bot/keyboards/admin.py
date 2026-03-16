from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Онлайн", callback_data="menu:online")
    kb.button(text="Статистика сервера", callback_data="menu:serverstats:week")
    kb.button(text="Расширенная статистика", callback_data="menu:extendedstats")
    kb.button(text="ChatWatch ON/OFF", callback_data="menu:chatwatch_toggle")
    kb.button(text="Оповещения ON/OFF", callback_data="menu:alerts")
    kb.adjust(1)
    return kb.as_markup()


def user_actions_keyboard(client_clid: int, default_reason: str = "via_telegram") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Kick", callback_data=f"admin_action:kick:{client_clid}:{default_reason}")
    kb.button(text="Ban 1h", callback_data=f"admin_action:ban:{client_clid}:3600")
    kb.button(text="Poke", callback_data=f"admin_action:poke:{client_clid}:Привет")
    kb.adjust(2, 1)
    return kb.as_markup()
