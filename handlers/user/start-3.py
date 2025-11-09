"""
Start command handler - ULTRA SIMPLE VERSION
Place this file in: handlers/user/start.py
"""

import os
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

start_router = Router()


@start_router.message(Command("start"))
async def start_command(message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    
    # Check if admin
    admin_ids = os.getenv("ADMIN_ID_LIST", "").split(",")
    is_admin = str(user_id) in [aid.strip() for aid in admin_ids if aid.strip()]
    
    # Create keyboard
    if is_admin:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛍️ Alle Kategorien"), KeyboardButton(text="👤 Mein Profil")],
                [KeyboardButton(text="🛒 Warenkorb"), KeyboardButton(text="🔑 Admin Menu")]
            ],
            resize_keyboard=True
        )
        text = "👋 Willkommen Admin!\n\nNutze die Buttons unten:"
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛍️ Alle Kategorien"), KeyboardButton(text="👤 Mein Profil")],
                [KeyboardButton(text="🛒 Warenkorb"), KeyboardButton(text="ℹ️ Hilfe")]
            ],
            resize_keyboard=True
        )
        text = "👋 Willkommen im Shop!\n\nNutze die Buttons unten:"
    
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

