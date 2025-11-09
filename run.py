import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from handlers.admin.admin import admin_router
from handlers.user.all_categories import all_categories_router
from handlers.user.cart import cart_router
from handlers.user.my_profile import my_profile_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup(bot):
    env = os.getenv("RUNTIME_ENVIRONMENT", "PROD")
    
    if env == "DEV":
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("DEV mode active")
    else:
        path = os.getenv("WEBHOOK_PATH", "/webhook")
        url = os.getenv("BASE_WEBHOOK_URL", "")
        secret = os.getenv("WEBHOOK_SECRET_TOKEN", "")
        
        full_url = url + path
        
        await bot.set_webhook(
            url=full_url,
            drop_pending_updates=True,
            secret_token=secret
        )
        
        logger.info("Webhook set")


async def on_shutdown(bot):
    await bot.session.close()


def main():
    token = os.getenv("TOKEN")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    dp.include_router(admin_router)
    dp.include_router(all_categories_router)
    dp.include_router(cart_router)
    dp.include_router(my_profile_router)
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    env = os.getenv("RUNTIME_ENVIRONMENT", "PROD")
    
    if env == "DEV":
        asyncio.run(dp.start_polling(bot))
    else:
        host = "0.0.0.0"
        port = int(os.getenv("PORT", "8080"))
        path = os.getenv("WEBHOOK_PATH", "/webhook")
        secret = os.getenv("WEBHOOK_SECRET_TOKEN", "")
        
        app = web.Application()
        handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret)
        handler.register(app, path=path)
        setup_application(app, dp, bot=bot)
        
        logger.info("Starting server")
        web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    main()
