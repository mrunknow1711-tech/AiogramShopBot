"""
Start command handler for user registration
Place this file in: handlers/user/start.py
"""

from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from enums.bot_entity import BotEntity
from utils.localizator import Localizator

start_router = Router()


def get_main_menu_keyboard():
    """Create main menu keyboard for users"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=Localizator.get_text(BotEntity.USER, "all_categories")),
                KeyboardButton(text=Localizator.get_text(BotEntity.USER, "my_profile"))
            ],
            [
                KeyboardButton(text=Localizator.get_text(BotEntity.USER, "cart")),
                KeyboardButton(text=Localizator.get_text(BotEntity.USER, "help"))
            ]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_admin_menu_keyboard():
    """Create menu keyboard for admin users"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=Localizator.get_text(BotEntity.USER, "all_categories")),
                KeyboardButton(text=Localizator.get_text(BotEntity.USER, "my_profile"))
            ],
            [
                KeyboardButton(text=Localizator.get_text(BotEntity.USER, "cart")),
                KeyboardButton(text=Localizator.get_text(BotEntity.ADMIN, "menu"))
            ]
        ],
        resize_keyboard=True
    )
    return keyboard


@start_router.message(CommandStart())
async def start_command(message: Message, session: AsyncSession | Session):
    """
    Handle /start command
    Register new users or welcome back existing users
    """
    user_id = message.from_user.id
    
    # Check if user exists in database
    # If your project has a UserService, use it here:
    # from services.user import UserService
    # user_exists = await UserService.get_user(user_id, session)
    
    # For now, simple welcome message
    # Adjust based on your project's user registration logic
    
    # Check if user is admin
    admin_ids = os.getenv("ADMIN_ID_LIST", "").split(",")
    is_admin = str(user_id) in admin_ids
    
    if is_admin:
        keyboard = get_admin_menu_keyboard()
        welcome_text = f"👋 Welcome Admin!\n\n{Localizator.get_text(BotEntity.USER, 'welcome')}"
    else:
        keyboard = get_main_menu_keyboard()
        welcome_text = Localizator.get_text(BotEntity.USER, "welcome")
    
    await message.answer(
        text=welcome_text,
        reply_markup=keyboard
    )


@start_router.message(F.text == Localizator.get_text(BotEntity.USER, "help"))
async def help_command(message: Message):
    """Handle help button/command"""
    support_link = os.getenv("SUPPORT_LINK", "https://t.me/support")
    help_text = f"""
ℹ️ **Help & Support**

Use the menu buttons to navigate:
• 🛍️ All Categories - Browse products
• 👤 My Profile - View balance & history
• 🛒 Cart - Checkout items

Need assistance?
Contact support: {support_link}
    """
    await message.answer(help_text)
