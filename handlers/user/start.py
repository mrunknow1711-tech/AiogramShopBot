"""
Start command handler with Localizator integration
Place this file in: handlers/user/start.py
"""

import os
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from enums.bot_entity import BotEntity
from utils.localizator import Localizator

start_router = Router()


@start_router.message(Command("start"))
async def start_command(message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    
    # Check if admin
    admin_ids = os.getenv("ADMIN_ID_LIST", "").split(",")
    is_admin = str(user_id) in [aid.strip() for aid in admin_ids if aid.strip()]
    
    # Create keyboard with Localizator texts
    if is_admin:
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
        welcome_text = Localizator.get_text(BotEntity.USER, "welcome")
        text = f"👋 Willkommen Admin!\n\n{welcome_text}"
    else:
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
        text = Localizator.get_text(BotEntity.USER, "welcome")
    
    await message.answer(text, reply_markup=keyboard)


@start_router.message(Command("help"))
async def help_command(message: Message):
    """Handle /help command"""
    support = os.getenv("SUPPORT_LINK", "https://t.me/support")
    text = f"""
ℹ️ Hilfe

Nutze die Menü-Buttons zur Navigation.

Support: {support}
    """
    await message.answer(text)
