import logging
import traceback

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

redis = Redis(host=config.REDIS_HOST, password=config.REDIS_PASSWORD)
bot = Bot(config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=RedisStorage(redis))
app = FastAPI()
app.include_router(processing_router)


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway"""
    return {
        "status": "healthy",
        "webhook_url": config.WEBHOOK_URL,
        "bot_username": (await bot.get_me()).username
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
    await create_db_and_tables()
    
    # Set webhook
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != config.WEBHOOK_URL:
        await bot.set_webhook(
            url=config.WEBHOOK_URL,
            secret_token=config.WEBHOOK_SECRET_TOKEN
        )
        logging.info(f"✅ Webhook set to: {config.WEBHOOK_URL}")
    else:
        logging.info(f"✅ Webhook already set to: {config.WEBHOOK_URL}")
    
    # Notify admins
    for admin in config.ADMIN_ID_LIST:
        try:
            await bot.send_message(admin, f'🤖 Bot is running on Railway!\n\n🌐 Webhook: {config.WEBHOOK_URL}')
        except Exception as e:
            logging.warning(f"Could not notify admin {admin}: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    logging.warning('Shutting down..')
    await bot.delete_webhook()
    await dp.storage.close()
    logging.warning('Bye!')


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    traceback_str = traceback.format_exc()
    admin_notification = (
        f"Critical error caused by {exc}\n\n"
        f"Stack trace:\n{traceback_str}"
    )
    if len(admin_notification) > 4096:
        byte_array = bytearray(admin_notification, 'utf-8')
        admin_notification = BufferedInputFile(byte_array, "exception.txt")
    await NotificationService.send_to_admins(admin_notification, None)
    return JSONResponse(
        status_code=500,
        content={"message": f"An error occurred: {str(exc)}"},
    )


def main() -> None:
    logging.info(f"🚀 Starting bot on Railway...")
    logging.info(f"📍 Host: {config.WEBAPP_HOST}")
    logging.info(f"🔌 Port: {config.WEBAPP_PORT}")
    logging.info(f"🌐 Webhook: {config.WEBHOOK_URL}")
    uvicorn.run(app, host=config.WEBAPP_HOST, port=config.WEBAPP_PORT)
