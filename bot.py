import logging
import traceback
import os

from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile
import config
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request, status, HTTPException
from db import create_db_and_tables
import uvicorn
from fastapi.responses import JSONResponse
from processing.processing import processing_router
from services.notification import NotificationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher with MemoryStorage (no Redis needed)
bot = Bot(config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Import and register ALL handlers
logger.info("Registering handlers...")

try:
    from handlers.user.start import start_router
    dp.include_router(start_router)
    logger.info("✅ start_router registered")
except Exception as e:
    logger.error(f"❌ Failed to register start_router: {e}")

try:
    from handlers.admin.admin import admin_router
    dp.include_router(admin_router)
    logger.info("✅ admin_router registered")
except Exception as e:
    logger.error(f"❌ Failed to register admin_router: {e}")

try:
    from handlers.user.all_categories import all_categories_router
    dp.include_router(all_categories_router)
    logger.info("✅ all_categories_router registered")
except Exception as e:
    logger.error(f"❌ Failed to register all_categories_router: {e}")

try:
    from handlers.user.cart import cart_router
    dp.include_router(cart_router)
    logger.info("✅ cart_router registered")
except Exception as e:
    logger.error(f"❌ Failed to register cart_router: {e}")

try:
    from handlers.user.my_profile import my_profile_router
    dp.include_router(my_profile_router)
    logger.info("✅ my_profile_router registered")
except Exception as e:
    logger.error(f"❌ Failed to register my_profile_router: {e}")

logger.info("All handlers registered!")

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
    logger.info("🚀 Starting bot...")
    await create_db_and_tables()
    await bot.set_webhook(
        url=config.WEBHOOK_URL,
        secret_token=config.WEBHOOK_SECRET_TOKEN
    )
    logger.info(f"✅ Webhook set to: {config.WEBHOOK_URL}")
    logger.info("💾 Using MemoryStorage (no Redis)")
    
    for admin in config.ADMIN_ID_LIST:
        try:
            await bot.send_message(admin, '🚀 Bot is online on Railway!')
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
    logger.error(f"Exception: {exc}\n{traceback_str}")
    return JSONResponse(
        status_code=500,
        content={"message": f"Error: {str(exc)}"},
    )


def main() -> None:
    port = int(os.getenv("PORT", config.WEBAPP_PORT))
    host = config.WEBAPP_HOST
    logger.info(f"🌐 Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
