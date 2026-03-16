from __future__ import annotations

import asyncio

from app.bootstrap import AppContext, create_app_context
from app.core.logging import get_logger


async def _seed_defaults(ctx: AppContext) -> None:
    async with ctx.session_factory() as session:
        await ctx.services.permission.ensure_roles_seeded(session)
        bootstrap_ids = set(ctx.settings.bootstrap_admin_tg_ids) | set(ctx.settings.bot_admin_ids)
        for tg_id in bootstrap_ids:
            user = await ctx.services.users.ensure_system_user(session, tg_id, full_name=f"admin_{tg_id}")
            await ctx.services.permission.promote_admin(session, user.id)
        await session.commit()


async def main() -> None:
    log = get_logger(component="main")
    ctx = await create_app_context()

    async def on_startup(*_) -> None:
        await _seed_defaults(ctx)
        try:
            await ctx.services.teamspeak.connect()
        except Exception as exc:  # noqa: BLE001
            log.warning("ts3_connect_failed_on_startup", error=str(exc))
        await ctx.ts3_monitor.start()
        await ctx.tts_worker.start()
        await ctx.reports_worker.start()
        log.info("bot_started")

    async def on_shutdown(*_) -> None:
        await ctx.reports_worker.stop()
        await ctx.tts_worker.stop()
        await ctx.ts3_monitor.stop()
        if ctx.redis:
            await ctx.redis.aclose()
        await ctx.bot.session.close()
        await ctx.engine.dispose()
        log.info("bot_stopped")

    ctx.dp.startup.register(on_startup)
    ctx.dp.shutdown.register(on_shutdown)

    await ctx.dp.start_polling(ctx.bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
