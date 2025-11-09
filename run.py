import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Import your handlers and routers here
# from handlers import router
# from database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """Setup webhook on bot startup"""
    runtime_env = os.getenv("RUNTIME_ENVIRONMENT", "PROD").upper()
    
    if runtime_env == "DEV":
        logger.info("🔧 Development mode - using polling instead of webhook")
        # For local development, delete webhook and use polling
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted, polling mode active")
    else:
        # Production mode - Railway/Cloud deployment
        webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
        base_url = os.getenv("BASE_WEBHOOK_URL")
        webhook_secret = os.getenv("WEBHOOK_SECRET_TOKEN")
        
        if not base_url:
            raise ValueError("BASE_WEBHOOK_URL must be set for production deployment!")
        
        webhook_url = f"{base_url}{webhook_path}"
        
        # Set webhook
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            secret_token=webhook_secret,
            allowed_updates=["message", "callback_query", "inline_query"]
        )
        
        webhook_info = await bot.get_webhook_info()
        logger.info(f"✅ Webhook configured: {webhook_info.url}")
        logger.info(f"🌐 Listening on: {webhook_path}")


async def on_shutdown(bot: Bot) -> None:
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down bot...")
    await bot.session.close()


def main() -> None:
    """Main entry point"""
    # Get configuration from environment
    token = os.getenv("TOKEN")
    if not token:
        raise ValueError("TOKEN environment variable is required!")
    
    runtime_env = os.getenv("RUNTIME_ENVIRONMENT", "PROD").upper()
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Register your routers here
    # dp.include_router(router)
    
    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    if runtime_env == "DEV":
        # Development mode - use polling
        logger.info("🚀 Starting bot in DEVELOPMENT mode (polling)...")
        asyncio.run(dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()))
    else:
        # Production mode - use webhook
        logger.info("🚀 Starting bot in PRODUCTION mode (webhook)...")
        
        webapp_host = os.getenv("WEBAPP_HOST", "0.0.0.0")
        webapp_port = int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "8000")))
        webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
        
        # Setup aiohttp application
        app = web.Application()
        
        # Create webhook handler
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=os.getenv("WEBHOOK_SECRET_TOKEN")
        )
        
        # Register webhook handler
        webhook_requests_handler.register(app, path=webhook_path)
        
        # Setup application
        setup_application(app, dp, bot=bot)
        
        # Run web application
        logger.info(f"📡 Starting webhook server on {webapp_host}:{webapp_port}")
        web.run_app(app, host=webapp_host, port=webapp_port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
