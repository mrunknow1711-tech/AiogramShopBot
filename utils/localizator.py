import config
from enums.bot_entity import BotEntity


class Localizator:
    # Hard-coded English texts - no JSON files needed!
    TEXTS = {
        "admin": {
            "menu": "🔑 Admin Menu",
        },
        "user": {
            "all_categories": "🛍️ All Categories",
            "my_profile": "👤 My Profile",
            "faq": "❓ FAQ",
            "help": "💬 Help",
            "cart": "🛒 Cart",
            "faq_string": "Frequently Asked Questions:\n\nHow to buy?\n- Select a category and product\n- Choose quantity\n- Confirm purchase",
            "help_string": "Need help? Contact our support:",
            "help_button": "📞 Support",
        },
        "common": {
            "start_message": "👋 Welcome to our shop!\n\nSelect an option from the menu below:",
            "usd_symbol": "$",
            "usd_text": "USD",
            "eur_symbol": "€",
            "eur_text": "EUR",
            "btc_symbol": "₿",
            "btc_text": "BTC",
        }
    }

    @staticmethod
    def get_text(entity: BotEntity, key: str) -> str:
        try:
            if entity == BotEntity.ADMIN:
                return Localizator.TEXTS["admin"].get(key, f"[Missing: {key}]")
            elif entity == BotEntity.USER:
                return Localizator.TEXTS["user"].get(key, f"[Missing: {key}]")
            else:
                return Localizator.TEXTS["common"].get(key, f"[Missing: {key}]")
        except KeyError:
            return f"[Error: {key}]"

    @staticmethod
    def get_currency_symbol():
        try:
            return Localizator.get_text(BotEntity.COMMON, f"{config.CURRENCY.value.lower()}_symbol")
        except:
            return "$"

    @staticmethod
    def get_currency_text():
        try:
            return Localizator.get_text(BotEntity.COMMON, f"{config.CURRENCY.value.lower()}_text")
        except:
            return "USD"
