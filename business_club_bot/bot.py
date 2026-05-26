"""
Точка входа бота. Запуск:

    python bot.py

Перед запуском:
  1. Установите зависимости: pip install -r requirements.txt
  2. Скопируйте .env.example в .env и заполните BOT_TOKEN и ADMIN_IDS
  3. Запустите бота: python bot.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import ADMIN_IDS, BOT_TOKEN
from database import init_db
from handlers import admin as admin_handlers
from handlers import user as user_handlers
from messages import load_messages


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    log = logging.getLogger("bot")

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN не задан. Скопируйте .env.example в .env и впишите токен."
        )
    if not ADMIN_IDS:
        log.warning(
            "ADMIN_IDS пуст: админ-панель будет недоступна никому. "
            "Добавьте свой ID в .env (узнать ID можно командой /id в боте)."
        )

    init_db()
    load_messages()  # гарантируем существование messages.json

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Сначала админ-роутер (его FSM-фильтры специфичнее), потом пользовательский
    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)

    me = await bot.get_me()
    log.info("Бот запущен: @%s (id=%s)", me.username, me.id)
    log.info("Администраторы: %s", ADMIN_IDS or "не заданы")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nБот остановлен.")
