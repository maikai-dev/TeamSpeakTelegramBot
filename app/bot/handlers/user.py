from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import period_keyboard
from app.core.enums import PeriodType
from app.services.container import ServiceContainer

router = Router(name="user")


def _extract_args(text: str | None) -> str:
    if not text:
        return ""
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        return ""
    return parts[1].strip()


def _period_from_str(value: str, default: PeriodType = PeriodType.WEEK) -> PeriodType:
    try:
        return PeriodType(value)
    except ValueError:
        return default


@router.message(Command("online"))
async def cmd_online(message: Message, services: ServiceContainer) -> None:
    online = await services.teamspeak.get_online_clients()
    rows = [
        {
            "nickname": c.nickname,
            "uid": c.uid,
            "channel_id": c.channel_id,
            "channel_name": c.channel_name,
            "is_muted": c.is_muted,
            "is_deaf": c.is_deaf,
            "server_groups": c.server_groups,
            "channel_seconds": c.channel_joined_seconds,
        }
        for c in online
    ]
    await message.answer(await services.stats.online_report(rows))


@router.callback_query(F.data == "menu:online")
async def cb_online(callback: CallbackQuery, services: ServiceContainer) -> None:
    if callback.message:
        await cmd_online(callback.message, services)  # type: ignore[arg-type]
    await callback.answer()


@router.message(Command("whois"))
async def cmd_whois(message: Message, services: ServiceContainer, session) -> None:
    pattern = _extract_args(message.text)
    if not pattern:
        await message.answer("Использование: /whois <ник или uid>")
        return
    await message.answer(await services.teamspeak.whois(session, pattern))


@router.message(Command("mystats"))
async def cmd_mystats(message: Message, services: ServiceContainer, session, user) -> None:
    text = await services.stats.format_user_stats(session, user=user, period=PeriodType.WEEK)
    await message.answer(text, reply_markup=period_keyboard("menu:mystats"))


@router.callback_query(F.data.startswith("menu:mystats:"))
async def cb_mystats_period(callback: CallbackQuery, services: ServiceContainer, session, user) -> None:
    period_raw = callback.data.split(":")[-1]
    period = _period_from_str(period_raw, default=PeriodType.WEEK)
    text = await services.stats.format_user_stats(session, user=user, period=period)
    if callback.message:
        await callback.message.answer(text, reply_markup=period_keyboard("menu:mystats"))
    await callback.answer()


@router.message(Command("myonline"))
async def cmd_myonline(message: Message, services: ServiceContainer, session, user) -> None:
    await message.answer(await services.stats.online_today(session, user))


@router.message(Command("mymessages"))
async def cmd_mymessages(message: Message, services: ServiceContainer, session, user) -> None:
    await message.answer(await services.stats.messages_today(session, user))


@router.message(Command("top"))
async def cmd_top(message: Message, services: ServiceContainer, session) -> None:
    arg = _extract_args(message.text)
    period = _period_from_str(arg, default=PeriodType.DAY)
    text = await services.stats.format_top_online(session, period=period)
    await message.answer(text, reply_markup=period_keyboard("menu:top"))


@router.callback_query(F.data.startswith("menu:top:"))
async def cb_top_period(callback: CallbackQuery, services: ServiceContainer, session) -> None:
    period = _period_from_str(callback.data.split(":")[-1], default=PeriodType.DAY)
    text = await services.stats.format_top_online(session, period=period)
    if callback.message:
        await callback.message.answer(text, reply_markup=period_keyboard("menu:top"))
    await callback.answer()


@router.message(Command("lastseen"))
async def cmd_lastseen(message: Message, services: ServiceContainer, session) -> None:
    pattern = _extract_args(message.text)
    if not pattern:
        await message.answer("Использование: /lastseen <ник>")
        return
    await message.answer(await services.stats.last_seen(session, pattern))


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, services: ServiceContainer, session, user) -> None:
    pattern = _extract_args(message.text)
    if not pattern:
        await message.answer("Использование: /subscribe <ник>")
        return

    target_id, label = await services.teamspeak.find_client_for_subscription(session, pattern)
    await services.notifications.subscribe_user_online(
        session=session,
        subscriber_user_id=user.id,
        target_ts3_client_id=target_id,
        target_label=label,
    )
    await message.answer(f"Подписка активирована: {label}")


@router.message(Command("favuser"))
async def cmd_favuser(message: Message, services: ServiceContainer, session, user) -> None:
    pattern = _extract_args(message.text)
    if not pattern:
        await message.answer("Использование: /favuser <ник>")
        return

    target_id, label = await services.teamspeak.find_client_for_subscription(session, pattern)
    await services.notifications.subscribe_user_online(
        session=session,
        subscriber_user_id=user.id,
        target_ts3_client_id=target_id,
        target_label=label,
    )
    await message.answer(f"Добавлен избранный пользователь: {label}")


@router.message(Command("favchannel"))
async def cmd_favchannel(message: Message, services: ServiceContainer, session, user) -> None:
    args = _extract_args(message.text)
    if not args:
        await message.answer("Использование: /favchannel <channel_id>")
        return
    try:
        channel_id = int(args)
    except ValueError:
        await message.answer("channel_id должен быть числом")
        return

    await services.notifications.subscribe_channel_activity(
        session=session,
        subscriber_user_id=user.id,
        channel_id=channel_id,
        target_label=f"channel:{channel_id}",
    )
    await message.answer(f"Канал {channel_id} добавлен в избранные")


@router.message(Command("myfavs"))
async def cmd_myfavs(message: Message, services: ServiceContainer, session, user) -> None:
    subs = await services.notifications.list_subscriptions(session, user.id)
    if not subs:
        await message.answer("Список избранного пуст.")
        return

    lines = ["⭐ Ваши подписки/избранное:"]
    for sub in subs:
        if sub.subscription_type.value == "user_online":
            target_name = sub.target_label or (sub.target_client.nickname if sub.target_client else "unknown")
            lines.append(f"- USER: {target_name}")
        else:
            lines.append(f"- CHANNEL: {sub.channel_id}")
    await message.answer("\n".join(lines))


@router.callback_query(F.data == "menu:favs")
async def cb_favs(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.answer("Используйте /myfavs для просмотра избранного.")
    await callback.answer()
