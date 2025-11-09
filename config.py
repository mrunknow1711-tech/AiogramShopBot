import os
from dotenv import load_dotenv
from enums.currency import Currency
from enums.runtime_environment import RuntimeEnvironment

load_dotenv(".env")

# Runtime Environment
RUNTIME_ENVIRONMENT = RuntimeEnvironment(os.environ.get("RUNTIME_ENVIRONMENT", "PROD"))

# Webhook Configuration for Railway
if RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
    # DEV mode uses polling, no webhook needed
    WEBHOOK_HOST = "http://localhost"
else:
    # PROD mode (Railway) - get URL from environment
    WEBHOOK_HOST = os.environ.get("BASE_WEBHOOK_URL", "")

WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBHOOK_SECRET_TOKEN = os.environ.get("WEBHOOK_SECRET_TOKEN", "")

# Server Configuration
WEBAPP_HOST = os.environ.get("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.environ.get("PORT", os.environ.get("WEBAPP_PORT", "8080")))

# Bot Configuration
TOKEN = os.environ.get("TOKEN")
ADMIN_ID_LIST = os.environ.get("ADMIN_ID_LIST", "").split(',')
ADMIN_ID_LIST = [int(admin_id.strip()) for admin_id in ADMIN_ID_LIST if admin_id.strip()]
SUPPORT_LINK = os.environ.get("SUPPORT_LINK", "")

# Database Configuration
DB_ENCRYPTION = os.environ.get("DB_ENCRYPTION", "false").lower() == "true"
DB_NAME = os.environ.get("DB_NAME", "database.db")
DB_PASS = os.environ.get("DB_PASS", "")

# Bot Settings
PAGE_ENTRIES = int(os.environ.get("PAGE_ENTRIES", "8"))
BOT_LANGUAGE = os.environ.get("BOT_LANGUAGE", "en")
MULTIBOT = os.environ.get("MULTIBOT", "false").lower() == "true"
CURRENCY = Currency(os.environ.get("CURRENCY", "USD"))

# Payment API Configuration
KRYPTO_EXPRESS_API_KEY = os.environ.get("KRYPTO_EXPRESS_API_KEY", "")
KRYPTO_EXPRESS_API_URL = os.environ.get("KRYPTO_EXPRESS_API_URL", "")
KRYPTO_EXPRESS_API_SECRET = os.environ.get("KRYPTO_EXPRESS_API_SECRET", "")

# Redis Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
