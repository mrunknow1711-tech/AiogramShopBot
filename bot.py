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

# Import handlers
from handlers.admin.admin import admin_router
from handlers.user.all_categories import all_categories_router
from handlers.user.cart import cart_router
from handlers.user.my_profile import my_profile_router
from handlers.user.start import start_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis = Redis(host=config.REDIS_HOST, password=config.REDIS_PASSWORD)
bot = Bot(config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=RedisStorage(redis))

# Register routers
dp.include_router(start_router)
dp.include_router(admin_router)
dp.include_router(all_categories_router)
dp.include_router(cart_router)
dp.include_router(my_profile_router)

app = FastAPI()
app.include_router(processing_router)


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
    logger.info("Starting bot...")
    await create_db_and_tables()
    await bot.set_webhook(
        url=config.WEBHOOK_URL,
        secret_token=config.WEBHOOK_SECRET_TOKEN
    )
    logger.info(f"Webhook set to: {config.WEBHOOK_URL}")
    
    for admin in config.ADMIN_ID_LIST:
        try:
            await bot.send_message(admin, '🚀 Bot is now online on Railway!')
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
    port = int(os.getenv("PORT", config.WEBAPP_PORT))
    host = config.WEBAPP_HOST
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
