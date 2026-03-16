from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import admin_menu, user_main_menu
from app.core.constants import COMMANDS_ADMIN, COMMANDS_USER
from app.services.container import ServiceContainer

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: Message, services: ServiceContainer, session, user) -> None:
    is_admin = await services.permission.is_admin(session, user)
    text = (
        "Привет! Это TS3 Control Bot.\n"
        "Я отслеживаю онлайн TeamSpeak, собираю статистику и даю инструменты управления."
    )
    keyboard = admin_menu() if is_admin else user_main_menu()
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("help"))
async def cmd_help(message: Message, services: ServiceContainer, session, user) -> None:
    is_admin = await services.permission.is_admin(session, user)
    lines = ["Доступные команды:", ""]
    lines.append("Пользовательские:")
    lines.extend([f"/{cmd}" for cmd in COMMANDS_USER])
    if is_admin:
        lines.append("")
        lines.append("Админские:")
        lines.extend([f"/{cmd}" for cmd in COMMANDS_ADMIN])
    await message.answer("\n".join(lines))


@router.message(Command("ping"))
async def cmd_ping(message: Message, services: ServiceContainer, session) -> None:
    db_ok = True
    ts_ok = True
    redis_ok = await services.runtime.ping()

    try:
        await services.teamspeak.get_channels()
    except Exception:
        ts_ok = False

    if session is None:
        db_ok = False

    await message.answer(
        "\n".join(
            [
                "🏥 Healthcheck",
                f"DB: {'OK' if db_ok else 'FAIL'}",
                f"Redis: {'OK' if redis_ok else 'FAIL'}",
                f"TS3: {'OK' if ts_ok else 'FAIL'}",
            ]
        )
    )


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery, services: ServiceContainer, session, user) -> None:
    await cmd_help(callback.message, services, session, user)  # type: ignore[arg-type]
    await callback.answer()
