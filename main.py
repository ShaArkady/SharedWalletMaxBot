import asyncio
import logging
from maxapi import Bot, Dispatcher
from maxapi.enums.parse_mode import ParseMode

from config import settings
from database.db import init_db
from handlers.handlers import register_handlers

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    await init_db()

    bot = Bot(settings.bot_token, parse_mode=ParseMode.MARKDOWN)
    dp = Dispatcher()

    await register_handlers(dp)

    logger.info("Бот запущен!")
    await bot.delete_webhook()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
