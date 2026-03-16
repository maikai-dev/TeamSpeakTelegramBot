from aiogram import Router

from app.bot.handlers import admin, start, user


def get_routers() -> list[Router]:
    return [start.router, user.router, admin.router]
