import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Import handlers - adjust paths if needed
from handlers.admin.admin import admin_router
from handlers.user.all_categories import all_categories_router
from handlers.user.cart import cart_router
from handlers.user.my_profile import my_profile_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """Setup webhook on bot startup"""
    runtime_env = os.getenv("RUNTIME_ENVIRONMENT", "PROD").upper()
    
    if runtime_env == "DEV":
        logger.info("Development mode - using polling")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted, polling active")
    else:
        webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
        base_url = os.getenv("BASE_WEBHOOK_URL")
        webhook_secret = os.getenv("WEBHOOK_SECRET_TOKEN")
        
        if not base_url:
            raise ValueError("BASE_WEBHOOK_URL must be set!")
        
        webhook_url = f"{base_url}{webhook_path}"
        
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            secret_token=webhook_secret,
            allowed_updates=["message", "callback_query", "inline_query"]
        )
        
        info = await bot.get_webhook_info()
        logger.info(f"Webhook configured: {info.url}")
        logger.info(f"Listening on: {webhook_path}")


async def on_shutdown(bot: Bot) -> None:
    """Cleanup on shutdown"""
    logger.info("Shutting down bot...")
    await bot.session.close()


def main():
    """Main entry point"""
    token = os.getenv("TOKEN")
    if not token:
        raise ValueError("TOKEN environment variable required!")
    
    runtime_env = os.getenv("RUNTIME_ENVIRONMENT", "PROD").upper()
    
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Register routers
    dp.include_router(admin_router)
    dp.include_router(all_categories_router)
    dp.include_router(cart_router)
    dp.include_router(my_profile_router)
    
    # Register startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    if runtime_env == "DEV":
        logger.info("Starting bot in DEV mode (polling)")
        asyncio.run(dp.start_polling(bot))
    else:
        logger.info("Starting bot in PROD mode (webhook)")
        
        host = os.getenv("WEBAPP_HOST", "0.0.0.0")
        port = int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "8080")))
        webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
        
        app = web.Application()
        
        handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=os.getenv("WEBHOOK_SECRET_TOKEN")
        )
        
        handler.register(app, path=webhook_path)
        setup_application(app, dp, bot=bot)
        
        logger.info(f"Starting server on {host}:{port}")
        web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)        webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
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
    
    # Register all routers in proper order
    # Start handler should be first (if you create start.py)
    # dp.include_router(start_router)  # Uncomment after creating start.py
    
    # Admin router includes: announcement, inventory, user_management, statistics, wallet
    dp.include_router(admin_router)
    
    # User routers
    dp.include_router(all_categories_router)
    dp.include_router(cart_router)
    dp.include_router(my_profile_router)
    
    # Database middleware setup (if your project uses it)
    # Uncomment and adjust based on your database setup:
    # from database import session_middleware
    # dp.update.middleware(session_middleware)
    
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
