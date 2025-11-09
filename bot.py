import logging
import traceback
import os

from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BufferedInputFile
from redis.asyncio import Redis
import config
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request, status, HTTPException
from db import create_db_and_tables
import uvicorn
from fastapi.responses import JSONResponse
from processing.processing import processing_router
from services.notification import NotificationService

# Redis Connection - EINFACHSTE METHODE
REDIS_URL = os.getenv("REDIS_URL")

if REDIS_URL:
    # Railway setzt REDIS_URL automatisch!
    redis = Redis.from_url(REDIS_URL, decode_responses=False)
    logging.info(f"✅ Connected to Redis via REDIS_URL")
else:
    # Fallback: Nutze MemoryStorage wenn kein Redis verfügbar
    logging.warning("⚠️ REDIS_URL not found, using MemoryStorage")
    from aiogram.fsm.storage.memory import MemoryStorage
    redis = None

bot = Bot(config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Storage je nach Redis-Verfügbarkeit
if redis:
    dp = Dispatcher(storage=RedisStorage(redis))
else:
    dp = Dispatcher(storage=MemoryStorage())

app = FastAPI()
app.include_router(processing_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "online",
        "bot": "AiogramShopBot",
        "version": "2.0-railway",
        "storage": "Redis" if redis else "Memory"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway"""
    try:
        bot_info = await bot.get_me()
        webhook_info = await bot.get_webhook_info()
        
        # Redis Health Check
        redis_status = "disconnected"
        if redis:
            try:
                await redis.ping()
                redis_status = "connected"
            except Exception as e:
                redis_status = f"error: {str(e)}"
        
        return {
            "status": "healthy",
            "bot_username": bot_info.username,
            "webhook_url": webhook_info.url,
            "pending_updates": webhook_info.pending_update_count,
            "redis_status": redis_status,
            "storage_type": "Redis" if redis else "Memory"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.post(config.WEBHOOK_PATH)
async def webhook(request: Request):
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_token != config.WEBHOOK_SECRET_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        update_data = await request.json()
        await dp.feed_webhook_update(bot, update_data)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return {"status": "error"}, status.HTTP_500_INTERNAL_SERVER_ERROR


@app.on_event("startup")
async def on_startup():
    logging.info("🚀 Starting AiogramShopBot on Railway...")
    
    # Create database
    await create_db_and_tables()
    logging.info("✅ Database initialized")
    
    # Set webhook
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != config.WEBHOOK_URL:
        await bot.set_webhook(
            url=config.WEBHOOK_URL,
            secret_token=config.WEBHOOK_SECRET_TOKEN,
            drop_pending_updates=True
        )
        logging.info(f"✅ Webhook set to: {config.WEBHOOK_URL}")
    else:
        logging.info(f"✅ Webhook already configured: {config.WEBHOOK_URL}")
    
    # Get bot info
    bot_info = await bot.get_me()
    logging.info(f"✅ Bot: @{bot_info.username}")
    logging.info(f"📍 Host: {config.WEBAPP_HOST}:{config.WEBAPP_PORT}")
    logging.info(f"🌐 Webhook: {config.WEBHOOK_URL}")
    
    # Check Redis
    if redis:
        try:
            await redis.ping()
            logging.info("✅ Redis connection successful")
        except Exception as e:
            logging.warning(f"⚠️ Redis connection failed: {e}")
    else:
        logging.info("ℹ️ Using MemoryStorage (no Redis)")
    
    # Notify admins
    storage_info = "Redis ✅" if redis else "Memory (Redis nicht verfügbar)"
    startup_message = (
        f"🤖 <b>Bot Started!</b>\n\n"
        f"👤 Bot: @{bot_info.username}\n"
        f"🌐 Webhook: {config.WEBHOOK_URL}\n"
        f"📊 Environment: {config.RUNTIME_ENVIRONMENT.value}\n"
        f"💾 Database: {config.DB_NAME}\n"
        f"🗄️ Storage: {storage_info}"
    )
    
    for admin in config.ADMIN_ID_LIST:
        try:
            await bot.send_message(admin, startup_message)
        except Exception as e:
            logging.warning(f"Could not notify admin {admin}: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    logging.warning('🛑 Shutting down...')
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.storage.close()
    if redis:
        await redis.close()
    logging.warning('👋 Bye!')


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    traceback_str = traceback.format_exc()
    logging.error(f"❌ Exception: {exc}\n{traceback_str}")
    
    admin_notification = (
        f"❌ <b>Critical Error</b>\n\n"
        f"<b>Error:</b> {exc}\n\n"
        f"<b>Traceback:</b>\n<pre>{traceback_str[:3000]}</pre>"
    )
    
    if len(admin_notification) > 4096:
        byte_array = bytearray(traceback_str, 'utf-8')
        admin_notification = BufferedInputFile(byte_array, "exception.txt")
    
    try:
        await NotificationService.send_to_admins(admin_notification, None)
    except Exception as notify_error:
        logging.error(f"Could not send error notification: {notify_error}")
    
    return JSONResponse(
        status_code=500,
        content={"message": f"An error occurred: {str(exc)}"},
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logging.info("="*50)
    logging.info("🚂 AiogramShopBot Railway Edition")
    logging.info("="*50)
    
    uvicorn.run(
        app,
        host=config.WEBAPP_HOST,
        port=config.WEBAPP_PORT,
        log_level="info"
    )
