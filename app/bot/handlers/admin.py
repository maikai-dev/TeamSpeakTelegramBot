from __future__ import annotations

import uuid
from collections.abc import Callable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import admin_menu, period_keyboard
from app.core.enums import AdminActionType, NotificationType, PeriodType
from app.services.container import ServiceContainer

router = Router(name="admin")


class SayStates(StatesGroup):
    waiting_channel = State()
    waiting_text = State()
    waiting_confirm = State()


_PENDING_ACTIONS: dict[str, dict] = {}


def _extract_args(text: str | None) -> str:
    if not text:
        return ""
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        return ""
    return parts[1].strip()


async def _ensure_admin(message: Message, services: ServiceContainer, session, user, action: AdminActionType) -> bool:
    is_admin = await services.permission.is_admin(session, user)
    if is_admin:
        return True

    await message.answer("Эта команда доступна только администраторам.")
    await services.audit.log(
        session,
        admin_user_id=user.id,
        action_type=action,
        success=False,
        reason="permission_denied",
        payload={"source": "telegram"},
    )
    return False


async def _check_sensitive_rate(message: Message, services: ServiceContainer, settings) -> bool:
    key = f"sensitive:{message.from_user.id if message.from_user else 0}"
    allowed = await services.rate_limiter.check(
        key=key,
        limit=settings.bot_sensitive_rate_limit_per_minute,
        window_seconds=60,
    )
    if not allowed:
        await message.answer("Слишком много чувствительных команд. Попробуйте через минуту.")
        return False
    return True


def _build_confirm_keyboard(token: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=f"admin_confirm:{token}")
    kb.button(text="❌ Отмена", callback_data=f"admin_cancel:{token}")
    kb.adjust(2)
    return kb.as_markup()


async def _enqueue_action(action: dict) -> str:
    token = uuid.uuid4().hex[:10]
    _PENDING_ACTIONS[token] = action
    return token


@router.message(Command("admin"))
async def cmd_admin(message: Message, services: ServiceContainer, session, user) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.RELOAD_CONFIG):
        return
    await message.answer("Админ-панель", reply_markup=admin_menu())


@router.message(Command("alerts"))
async def cmd_alerts(message: Message, services: ServiceContainer, session, user) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.RELOAD_CONFIG):
        return

    lines = ["🔔 Управление алертами:"]
    for nt in [NotificationType.JOIN, NotificationType.LEAVE, NotificationType.MOVE, NotificationType.CHAT]:
        await services.notifications.toggle_notification(
            session=session,
            user_id=user.id,
            notification_type=nt,
            enabled=True,
        )
        lines.append(f"- {nt.value}: включено")
    lines.append("Точная настройка quiet hours доступна через таблицу notification_settings.")
    await message.answer("\n".join(lines))


@router.message(Command("chatwatch"))
async def cmd_chatwatch(message: Message, services: ServiceContainer, session, user) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.CHATWATCH_TOGGLE):
        return

    enabled = await services.runtime.toggle_chatwatch()
    await services.audit.log(
        session,
        admin_user_id=user.id,
        action_type=AdminActionType.CHATWATCH_TOGGLE,
        success=True,
        payload={"enabled": enabled},
    )
    await message.answer(f"ChatWatch {'включен' if enabled else 'выключен'}.")


@router.callback_query(F.data == "menu:chatwatch_toggle")
async def cb_chatwatch(callback: CallbackQuery, services: ServiceContainer, session, user) -> None:
    if not callback.message:
        await callback.answer()
        return
    await cmd_chatwatch(callback.message, services, session, user)  # type: ignore[arg-type]
    await callback.answer()


@router.callback_query(F.data == "menu:alerts")
async def cb_alerts(callback: CallbackQuery, services: ServiceContainer, session, user) -> None:
    if not callback.message:
        await callback.answer()
        return
    await cmd_alerts(callback.message, services, session, user)  # type: ignore[arg-type]
    await callback.answer()


@router.message(Command("serverstats"))
async def cmd_serverstats(message: Message, services: ServiceContainer, session, user) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.RELOAD_CONFIG):
        return
    arg = _extract_args(message.text)
    period = PeriodType(arg) if arg in PeriodType._value2member_map_ else PeriodType.WEEK
    text = await services.stats.server_stats_full(session, period=period)
    await message.answer(text, reply_markup=period_keyboard("menu:serverstats"))


@router.callback_query(F.data.startswith("menu:serverstats:"))
async def cb_serverstats(callback: CallbackQuery, services: ServiceContainer, session, user) -> None:
    if not callback.message:
        await callback.answer()
        return
    if not await services.permission.is_admin(session, user):
        await callback.answer("Нет прав", show_alert=True)
        return
    period_raw = callback.data.split(":")[-1]
    period = PeriodType(period_raw) if period_raw in PeriodType._value2member_map_ else PeriodType.WEEK
    text = await services.stats.server_stats_full(session, period=period)
    await callback.message.answer(text, reply_markup=period_keyboard("menu:serverstats"))
    await callback.answer()


@router.callback_query(F.data == "menu:extendedstats")
async def cb_extended_stats(callback: CallbackQuery, services: ServiceContainer, session, user) -> None:
    if not callback.message:
        await callback.answer()
        return
    if not await services.permission.is_admin(session, user):
        await callback.answer("Нет прав", show_alert=True)
        return

    sections = await services.stats.extended_stats_sections(session)
    for key in sorted(sections.keys()):
        await callback.message.answer(sections[key])
    await callback.answer()


async def _select_client_action(
    message: Message,
    services: ServiceContainer,
    pattern: str,
    action_builder: Callable[[int, str], dict],
) -> None:
    candidates = await services.teamspeak.find_online_clients(pattern)
    if not candidates:
        await message.answer("Подходящий онлайн-пользователь не найден.")
        return

    if len(candidates) == 1:
        action = action_builder(candidates[0].clid, candidates[0].nickname)
        token = await _enqueue_action(action)
        await message.answer(
            f"Подтвердите действие для {candidates[0].nickname}",
            reply_markup=_build_confirm_keyboard(token),
        )
        return

    kb = InlineKeyboardBuilder()
    for client in candidates[:8]:
        action = action_builder(client.clid, client.nickname)
        token = await _enqueue_action(action)
        kb.button(text=f"{client.nickname} ({client.channel_name})", callback_data=f"admin_confirm:{token}")
    kb.adjust(1)
    await message.answer("Найдено несколько пользователей. Выберите:", reply_markup=kb.as_markup())


@router.message(Command("kick"))
async def cmd_kick(message: Message, services: ServiceContainer, session, user, settings) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.KICK):
        return
    if not await _check_sensitive_rate(message, services, settings):
        return

    args = _extract_args(message.text)
    if not args:
        await message.answer("Использование: /kick <ник> [причина]")
        return

    chunks = args.split(maxsplit=1)
    pattern = chunks[0]
    reason = chunks[1] if len(chunks) > 1 else "kick via telegram"

    await _select_client_action(
        message,
        services,
        pattern,
        lambda clid, nickname: {
            "type": "kick",
            "clid": clid,
            "nickname": nickname,
            "reason": reason,
            "admin_user_id": user.id,
            "admin_tg_id": user.telegram_id,
        },
    )


@router.message(Command("ban"))
async def cmd_ban(message: Message, services: ServiceContainer, session, user, settings) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.BAN):
        return
    if not await _check_sensitive_rate(message, services, settings):
        return

    args = _extract_args(message.text)
    if not args:
        await message.answer("Использование: /ban <ник> [часы=24] [причина]")
        return

    parts = args.split()
    pattern = parts[0]
    hours = 24
    reason = "ban via telegram"
    if len(parts) >= 2 and parts[1].isdigit():
        hours = max(1, int(parts[1]))
        if len(parts) >= 3:
            reason = " ".join(parts[2:])
    elif len(parts) >= 2:
        reason = " ".join(parts[1:])

    duration_seconds = hours * 3600

    await _select_client_action(
        message,
        services,
        pattern,
        lambda clid, nickname: {
            "type": "ban",
            "clid": clid,
            "nickname": nickname,
            "reason": reason,
            "duration": duration_seconds,
            "admin_user_id": user.id,
            "admin_tg_id": user.telegram_id,
        },
    )


@router.message(Command("move"))
async def cmd_move(message: Message, services: ServiceContainer, session, user, settings) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.MOVE):
        return
    if not await _check_sensitive_rate(message, services, settings):
        return

    args = _extract_args(message.text)
    parts = args.split()
    if len(parts) < 2:
        await message.answer("Использование: /move <ник> <channel_id>")
        return

    pattern = parts[0]
    try:
        channel_id = int(parts[1])
    except ValueError:
        await message.answer("channel_id должен быть числом")
        return

    await _select_client_action(
        message,
        services,
        pattern,
        lambda clid, nickname: {
            "type": "move",
            "clid": clid,
            "nickname": nickname,
            "channel_id": channel_id,
            "admin_user_id": user.id,
            "admin_tg_id": user.telegram_id,
        },
    )


@router.message(Command("poke"))
async def cmd_poke(message: Message, services: ServiceContainer, session, user) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.POKE):
        return
    args = _extract_args(message.text)
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /poke <ник> <сообщение>")
        return

    pattern, poke_message = parts[0], parts[1]
    candidates = await services.teamspeak.find_online_clients(pattern)
    if not candidates:
        await message.answer("Пользователь не найден онлайн")
        return

    target = candidates[0]
    await services.teamspeak.poke_client(target.clid, poke_message)
    await services.audit.log(
        session,
        admin_user_id=user.id,
        action_type=AdminActionType.POKE,
        success=True,
        target_label=target.nickname,
        reason=poke_message,
    )
    await message.answer(f"Poke отправлен: {target.nickname}")


@router.message(Command("mute"))
async def cmd_mute(message: Message, services: ServiceContainer, session, user, settings) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.MUTE):
        return
    if not await _check_sensitive_rate(message, services, settings):
        return

    args = _extract_args(message.text)
    if not args:
        await message.answer("Использование: /mute <ник>")
        return

    await _select_client_action(
        message,
        services,
        args,
        lambda clid, nickname: {
            "type": "mute",
            "clid": clid,
            "nickname": nickname,
            "admin_user_id": user.id,
            "admin_tg_id": user.telegram_id,
        },
    )


@router.message(Command("groupadd"))
async def cmd_groupadd(message: Message, services: ServiceContainer, session, user, settings) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.ASSIGN_GROUP):
        return
    if not await _check_sensitive_rate(message, services, settings):
        return

    args = _extract_args(message.text).split()
    if len(args) < 2:
        await message.answer("Использование: /groupadd <ник> <sgid>")
        return

    pattern = args[0]
    try:
        sgid = int(args[1])
    except ValueError:
        await message.answer("sgid должен быть числом")
        return

    await _select_client_action(
        message,
        services,
        pattern,
        lambda clid, nickname: {
            "type": "groupadd",
            "clid": clid,
            "nickname": nickname,
            "sgid": sgid,
            "admin_user_id": user.id,
            "admin_tg_id": user.telegram_id,
        },
    )


@router.message(Command("groupdel"))
async def cmd_groupdel(message: Message, services: ServiceContainer, session, user, settings) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.REMOVE_GROUP):
        return
    if not await _check_sensitive_rate(message, services, settings):
        return

    args = _extract_args(message.text).split()
    if len(args) < 2:
        await message.answer("Использование: /groupdel <ник> <sgid>")
        return

    pattern = args[0]
    try:
        sgid = int(args[1])
    except ValueError:
        await message.answer("sgid должен быть числом")
        return

    await _select_client_action(
        message,
        services,
        pattern,
        lambda clid, nickname: {
            "type": "groupdel",
            "clid": clid,
            "nickname": nickname,
            "sgid": sgid,
            "admin_user_id": user.id,
            "admin_tg_id": user.telegram_id,
        },
    )


@router.message(Command("reloadconfig"))
async def cmd_reload_config(message: Message, services: ServiceContainer, session, user) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.RELOAD_CONFIG):
        return

    # Для .env требуется рестарт процесса, но runtime-флаги обновляются без перезапуска.
    await services.audit.log(
        session,
        admin_user_id=user.id,
        action_type=AdminActionType.RELOAD_CONFIG,
        success=True,
        reason="runtime_only",
    )
    await message.answer("Runtime конфиг обновлен. Для переменных .env нужен перезапуск контейнера.")


@router.callback_query(F.data.startswith("admin_confirm:"))
async def cb_admin_confirm(callback: CallbackQuery, services: ServiceContainer, session, user) -> None:
    token = callback.data.split(":", 1)[1]
    action = _PENDING_ACTIONS.pop(token, None)
    if not action:
        await callback.answer("Сессия действия истекла", show_alert=True)
        return

    if user.telegram_id != action.get("admin_tg_id"):
        await callback.answer("Подтверждать может только инициатор", show_alert=True)
        return

    if not await services.permission.is_admin(session, user):
        await callback.answer("Нет прав", show_alert=True)
        return

    action_type_map = {
        "kick": AdminActionType.KICK,
        "ban": AdminActionType.BAN,
        "move": AdminActionType.MOVE,
        "mute": AdminActionType.MUTE,
        "groupadd": AdminActionType.ASSIGN_GROUP,
        "groupdel": AdminActionType.REMOVE_GROUP,
    }

    kind = action["type"]
    clid = int(action["clid"])
    nickname = action["nickname"]

    try:
        if kind == "kick":
            await services.teamspeak.kick_client(clid, action["reason"])
        elif kind == "ban":
            await services.teamspeak.ban_client(clid, int(action["duration"]), action["reason"])
        elif kind == "move":
            await services.teamspeak.move_client(clid, int(action["channel_id"]))
        elif kind == "mute":
            await services.teamspeak.set_client_mute(clid, True)
        elif kind == "groupadd":
            await services.teamspeak.assign_group_by_clid(clid, int(action["sgid"]))
        elif kind == "groupdel":
            await services.teamspeak.remove_group_by_clid(clid, int(action["sgid"]))
        else:
            raise RuntimeError(f"Неизвестный тип действия: {kind}")

        await services.audit.log(
            session,
            admin_user_id=user.id,
            action_type=action_type_map.get(kind, AdminActionType.RELOAD_CONFIG),
            success=True,
            target_label=nickname,
            payload=action,
        )
        if callback.message:
            await callback.message.answer(f"Действие {kind} выполнено для {nickname}")
        await callback.answer("Готово")
    except Exception as exc:  # noqa: BLE001
        await services.audit.log(
            session,
            admin_user_id=user.id,
            action_type=action_type_map.get(kind, AdminActionType.RELOAD_CONFIG),
            success=False,
            target_label=nickname,
            reason=str(exc),
            payload=action,
        )
        if callback.message:
            await callback.message.answer(f"Ошибка: {exc}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin_cancel:"))
async def cb_admin_cancel(callback: CallbackQuery) -> None:
    token = callback.data.split(":", 1)[1]
    _PENDING_ACTIONS.pop(token, None)
    await callback.answer("Отменено")


@router.message(Command("say"))
async def cmd_say(message: Message, services: ServiceContainer, session, user, state: FSMContext, settings) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.TTS):
        return
    if not await _check_sensitive_rate(message, services, settings):
        return

    await state.set_state(SayStates.waiting_channel)
    await message.answer("Введите channel_id для озвучки:")


@router.message(SayStates.waiting_channel)
async def say_waiting_channel(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужен числовой channel_id. Попробуйте снова:")
        return
    await state.update_data(channel_id=int(text))
    await state.set_state(SayStates.waiting_text)
    await message.answer("Введите текст для озвучки:")


@router.message(SayStates.waiting_text)
async def say_waiting_text(message: Message, state: FSMContext, settings) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым")
        return
    if len(text) > settings.bot_max_tts_text_length:
        await message.answer(f"Слишком длинный текст. Лимит: {settings.bot_max_tts_text_length} символов")
        return
    await state.update_data(tts_text=text)
    data = await state.get_data()
    channel_id = data["channel_id"]

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Отправить", callback_data="say:confirm")
    kb.button(text="❌ Отмена", callback_data="say:cancel")
    kb.adjust(2)

    await state.set_state(SayStates.waiting_confirm)
    await message.answer(
        f"Предпросмотр TTS:\nКанал: {channel_id}\nТекст: {text}",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "say:confirm", SayStates.waiting_confirm)
async def say_confirm(callback: CallbackQuery, services: ServiceContainer, session, user, state: FSMContext) -> None:
    data = await state.get_data()
    channel_id = int(data["channel_id"])
    text = str(data["tts_text"])

    job = await services.tts.create_job(
        session=session,
        requested_by_user_id=user.id,
        channel_id=channel_id,
        channel_name=None,
        text=text,
    )
    await services.audit.log(
        session,
        admin_user_id=user.id,
        action_type=AdminActionType.TTS,
        success=True,
        reason=text,
        payload={"channel_id": channel_id, "job_id": job.id},
    )
    await state.clear()
    if callback.message:
        await callback.message.answer(f"TTS задача создана: #{job.id}")
    await callback.answer("TTS отправлен")


@router.callback_query(F.data == "say:cancel", SayStates.waiting_confirm)
async def say_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.answer("Отменено")
    await callback.answer()


@router.message(Command("userstats"))
async def cmd_userstats(message: Message, services: ServiceContainer, session, user) -> None:
    if not await _ensure_admin(message, services, session, user, AdminActionType.RELOAD_CONFIG):
        return

    pattern = _extract_args(message.text)
    if not pattern:
        await message.answer("Использование: /userstats <ник>")
        return

    rows = await services.stats.export_user_stats_csv(session, pattern)
    if not rows:
        await message.answer("Нет данных по пользователю")
        return

    from app.utils.csv_export import to_csv_bytes

    csv_data = to_csv_bytes(rows)
    await message.answer_document(
        document=BufferedInputFile(csv_data, filename=f"stats_{pattern}.csv"),
        caption=f"CSV-экспорт статистики для {pattern}",
    )
