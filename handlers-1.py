"""

Telegram Handler für Werbung-Modul - VOLLSTÄNDIG KORRIGIERT

FIXES:

✅ Minuten-Eingabe funktioniert jetzt korrekt

✅ Gruppen-Mehrfachauswahl beim Bearbeiten (erstellt Kopien)

✅ Media (Bild/Video) ändern Funktion hinzugefügt

✅ Alle Handler korrekt registriert

MINUTEN-SYSTEM (1-1440 Min):

- ✅ intervall_hours speichert MINUTEN

- ✅ Button "Alle Xh" → "Alle X Min"

- ✅ Eingabe nur in Minuten (1-1440)

"""

import logging

import re

from typing import List, Optional, Dict, Tuple

from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import (

    ContextTypes, CommandHandler, MessageHandler, 

    CallbackQueryHandler, ConversationHandler, filters

)

from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut

from modules.werbung.gemini_integration import create_werbung_with_gemini, regenerate_werbung

from modules.werbung.database import WerbungDB, WerbungPostDB

from modules.werbung.scheduler import get_scheduler

from modules.werbung.minimizer import expand_ad, minimize_ad, post_minimized_ad

from database.models import UserModel, ActionLogModel

from shared.group_handler import get_active_groups

from shared.menu_system import MenuSystem

from config.constants import (

    UserState, WerbeTyp, Emoji, IntervallTyp, 

    CallbackPrefix, InfoMessages, ErrorMessages, SuccessMessages, PostType

)

from config.settings import WERBUNG_SETTINGS, RATE_LIMITS

logger = logging.getLogger(__name__)

PLATFORM_PATTERNS = {

    'gateway': {

        'pattern': r'(?:(\w+)\s+(?:Gateway|Kanal)\s+(@\w+)|(?:Gateway|Kanal)\s+(\w+)\s+(@\w+))',

        'emoji': '📢',

        'url_template': 'https://t.me/{username}',

        'extract_name': True

    },

    'shop': {

        'pattern': r'Shop\s+(@\w+)',

        'emoji': '🛍️',

        'url_template': 'https://t.me/{username}',

        'extract_from_link': True

    },

    'telegram': {

        'pattern': r'(?:Telegram|Kontakt)\s+(@\w+)',

        'emoji': '💬',

        'url_template': 'https://t.me/{username}',

        'button_label': 'Kontakt'

    },

    'bot': {

        'pattern': r'(?:Bot|Support)\s+(@\w+)',

        'emoji': '🏛️',

        'url_template': 'https://t.me/{username}',

        'button_label': 'Support'

    },

    'threema': {

        'pattern': r'Threema\s+([A-Z0-9]{8})',

        'emoji': '🔐',

        'url_template': 'https://threema.id/{id}',

        'button_label': 'Threema'

    },

    'signal': {

        'pattern': r'Signal\s+(\+\d{10,15})',

        'emoji': '📱',

        'url_template': 'https://signal.me/#p/{phone}',

        'button_label': 'Signal'

    },

    'whatsapp': {

        'pattern': r'WhatsApp\s+(\+\d{10,15})',

        'emoji': '💚',

        'url_template': 'https://wa.me/{phone}',

        'button_label': 'WhatsApp'

    }

}

class WerbungHandler:

    """Handler für Werbungs-Funktionen"""

    

    WAITING_INPUT = 1

    PREVIEW = 2

    SETTINGS = 3

    TIMER_INPUT = 4

    MINUTES_INPUT = 5

    START_DATE_INPUT = 6

    END_DATE_INPUT = 7

    MANUAL_BUTTON_TEXT = 8

    MANUAL_BUTTON_URL = 9

    EDIT_TEXT_INPUT = 10

    EDIT_MINUTES_INPUT = 11

    

    def __init__(self):

        self.user_data_cache = {}

    

    async def _safe_answer_callback(self, query, text: str = None, show_alert: bool = False):

        """Sicheres answer_callback_query mit Timeout-Handling"""

        try:

            await query.answer(text=text, show_alert=show_alert)

        except TimedOut:

            logger.warning(f"⚠️ Callback answer timeout (nicht kritisch)")

        except Exception as e:

            logger.debug(f"Callback answer error: {e}")

    

    async def _send_message_safe(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, 

                                 text: str, reply_markup=None, parse_mode='Markdown'):

        """Sendet Message sicher mit Fallback auf plain text"""

        try:

            return await context.bot.send_message(

                chat_id=chat_id,

                text=text,

                reply_markup=reply_markup,

                parse_mode=parse_mode

            )

        except BadRequest as e:

            if "can't parse entities" in str(e).lower():

                logger.warning(f"⚠️ Markdown-Parse-Error, versuche ohne parse_mode")

                return await context.bot.send_message(

                    chat_id=chat_id,

                    text=text,

                    reply_markup=reply_markup,

                    parse_mode=None

                )

            else:

                raise

    

    async def _cleanup_messages(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_ids: List[int]):

        """Löscht mehrere Messages"""

        for msg_id in message_ids:

            try:

                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)

            except Exception as e:

                logger.debug(f"Konnte Message {msg_id} nicht löschen: {e}")

    

    def _extract_smart_buttons(self, text: str) -> List[Dict[str, str]]:

        """Extrahiert automatisch Buttons aus Text mit dynamischen Namen"""

        buttons = []

        

        for platform, config in PLATFORM_PATTERNS.items():

            pattern = config['pattern']

            matches = re.finditer(pattern, text, re.IGNORECASE)

            

            for match in matches:

                button_text = None

                url = None

                

                if platform == 'gateway':

                    if match.group(1):

                        name = match.group(1)

                        username = match.group(2).lstrip('@')

                    else:

                        name = match.group(3)

                        username = match.group(4).lstrip('@')

                    

                    url = config['url_template'].format(username=username)

                    button_text = f"{config['emoji']} {name}"

                    

                    logger.info(f"✅ Gateway Button erkannt: '{name}' -> {url}")

                    

                elif platform == 'shop':

                    username = match.group(1).lstrip('@')

                    url = config['url_template'].format(username=username)

                    button_text = f"{config['emoji']} {username}"

                    

                elif platform in ['telegram', 'bot']:

                    username = match.group(1).lstrip('@')

                    url = config['url_template'].format(username=username)

                    button_text = f"{config['emoji']} {config['button_label']}"

                    

                elif platform == 'threema':

                    threema_id = match.group(1)

                    url = config['url_template'].format(id=threema_id)

                    button_text = f"{config['emoji']} {config['button_label']}"

                    

                elif platform == 'signal':

                    phone = match.group(1)

                    url = config['url_template'].format(phone=phone)

                    button_text = f"{config['emoji']} {config['button_label']}"

                    

                elif platform == 'whatsapp':

                    phone = match.group(1).replace('+', '')

                    url = config['url_template'].format(phone=phone)

                    button_text = f"{config['emoji']} {config['button_label']}"

                

                if button_text and url:

                    buttons.append({

                        'text': button_text,

                        'url': url,

                        'platform': platform

                    })

                    logger.info(f"✅ Button erkannt: {button_text} → {url}")

        

        return buttons

    

    def _extract_generic_links(self, text: str) -> List[Dict[str, str]]:

        """Extrahiert generische URLs aus Text"""

        buttons = []

        

        url_pattern = r'https?://[^\s]+'

        urls = re.findall(url_pattern, text)

        

        for url in urls:

            is_platform_url = False

            for platform_config in PLATFORM_PATTERNS.values():

                if any(domain in url for domain in ['t.me', 'threema.id', 'signal.me', 'viber://', 'wa.me']):

                    is_platform_url = True

                    break

            

            if not is_platform_url:

                domain = url.split('/')[2] if len(url.split('/')) > 2 else 'Link'

                button_text = f"🔗 {domain}"

                

                buttons.append({

                    'text': button_text,

                    'url': url,

                    'platform': 'generic'

                })

                

                logger.info(f"✅ Generischer Button erkannt: {button_text} → {url}")

        

        return buttons

    

    def _create_button_layout(self, buttons: List[InlineKeyboardButton]) -> List[List[InlineKeyboardButton]]:

        """Erstellt 2-Spalten Button-Layout"""

        keyboard = []

        

        for i in range(0, len(buttons), 2):

            if i + 1 < len(buttons):

                keyboard.append([buttons[i], buttons[i + 1]])

            else:

                keyboard.append([buttons[i]])

        

        return keyboard

    

    def _parse_date(self, date_str: str) -> Optional[datetime]:

        """Parst Datum im Format DD.MM.YYYY"""

        try:

            return datetime.strptime(date_str.strip(), '%d.%m.%Y')

        except ValueError:

            return None

    

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """/start Command"""

        if update.effective_chat.type == 'private':

            await MenuSystem.show_main_menu(update, context)

        else:

            await update.message.reply_text("✅ Bot ist aktiv!")

    

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """/help Command"""

        keyboard = MenuSystem.create_main_menu_keyboard()

        

        await update.message.reply_text(

            f"ℹ️ **Hilfe - Werbung-Bot**\n\n"

            "**Werbung erstellen:**\n"

            "1. Klicke 📢 Werbung\n"

            "2. Schicke Text, Bilder und Links\n"

            "3. Klicke 'Fertig'\n"

            "4. Prüfe die Vorschau\n"

            "5. Wähle Zielgruppe(n)\n"

            "6. Wähle Posting-Optionen\n"

            "7. Poste!\n\n"

            "**Features:**\n"

            f"{Emoji.AD} KI-generierte stylische Werbungen\n"

            f"{Emoji.IMAGE} Bilder & Videos unterstützt\n"

            f"{Emoji.LINK} Automatische Button-Erkennung\n"

            f"{Emoji.TIMER} Intervall-Posts (Minuten-basiert)\n"

            f"{Emoji.PIN} Werbungen anheften\n"

            f"{Emoji.DELETE} Alte Posts automatisch löschen\n\n"

            "**Befehle:**\n"

            "/start - Hauptmenü\n"

            "/help - Diese Hilfe\n"

            "/groups - Gruppen verwalten",

            reply_markup=keyboard,

            parse_mode='Markdown'

        )

    

    async def cmd_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """/groups Command"""

        await MenuSystem.handle_menu_gruppen(update, context)

    

    async def cmd_werbe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """/werbe Command"""

        if update.effective_chat.type != 'private':

            await update.message.reply_text("⚠️ Bitte schreib mir privat, um Werbung zu erstellen!")

            return ConversationHandler.END

        

        user = update.effective_user

        

        UserModel.get_or_create(user.id, user.username, user.first_name)

        

        if not UserModel.check_rate_limit(user.id, 'werbe', RATE_LIMITS['werbe_per_hour'], 60):

            keyboard = MenuSystem.create_main_menu_keyboard()

            await update.message.reply_text(

                ErrorMessages.RATE_LIMIT.format(minutes=60),

                reply_markup=keyboard

            )

            return ConversationHandler.END

        

        ActionLogModel.log(user.id, 'werbe_start')

        

        self.user_data_cache[user.id] = {

            'text': '',

            'urls': [],

            'media_ids': [],

            'media_type': None,

            'werbetyp': WerbeTyp.CUSTOM,

            'expand_timer_seconds': WERBUNG_SETTINGS['expanded_ad_ttl'],

            'bot_messages': [],

            'user_messages': [],

            'selected_groups': [],

            'start_date': None,

            'end_date': None,

            'manual_buttons': [],

            'detected_buttons': [],

            'temp_button_text': None,

            'pin_enabled': False,

            'delete_old': True

        }

        

        if update.message and not update.message.text.startswith("📢 Werbung"):

            self.user_data_cache[user.id]['user_messages'].append(update.message.message_id)

        

        keyboard = [[InlineKeyboardButton(f"{Emoji.CROSS} Abbrechen", callback_data="werbe_cancel")]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        msg = await update.message.reply_text(

            f"📣 **Werbung erstellen**\n\n"

            f"━━━━━━━━━━━━━━━━\n\n"

            f"Schick mir deinen Werbetext mit:\n\n"

            f"🖼️ **Bilder/Videos** (optional)\n"

            f"🔗 **Links** (werden automatisch erkannt)\n"

            f"📝 **Deinen Werbetext**\n\n"

            f"**Unterstützte Plattformen:**\n"

            f"• Gateway/Kanal Name @link → 📢 Name\n"

            f"• Shop @link → 🛍️ Shopname\n"

            f"• Bot/Support @username → 🏛️ Support\n"

            f"• Telegram/Kontakt @username → 💬 Kontakt\n"

            f"• Threema ID → 🔐 Threema\n"

            f"• Signal +49... → 📱 Signal\n"

            f"• WhatsApp +49... → 💚 WhatsApp\n\n"

            f"Ich erstelle daraus automatisch Buttons!",

            reply_markup=reply_markup,

            parse_mode='Markdown'

        )

        

        self.user_data_cache[user.id]['bot_messages'].append(msg.message_id)

        

        logger.info(f"✅ ConversationHandler gestartet für User {user.id}")

        return self.WAITING_INPUT

    

    async def handle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Empfängt User-Input"""

        user = update.effective_user

        message = update.message

        

        if message.text and message.text.startswith("📢 Werbung"):

            logger.info(f"⏭️ Ignoriere Kachel-Button Text")

            return self.WAITING_INPUT

        

        if user.id not in self.user_data_cache:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await message.reply_text("Bitte starte neu.", reply_markup=keyboard)

            return ConversationHandler.END

        

        user_data = self.user_data_cache[user.id]

        user_data['user_messages'].append(message.message_id)

        

        if message.text:

            user_data['text'] += message.text + "\n"

            urls = re.findall(r'https?://[^\s]+', message.text)

            user_data['urls'].extend(urls)

        

        if message.caption:

            user_data['text'] += message.caption + "\n"

            urls = re.findall(r'https?://[^\s]+', message.caption)

            user_data['urls'].extend(urls)

        

        if message.photo:

            file_id = message.photo[-1].file_id

            user_data['media_ids'].append(file_id)

            user_data['media_type'] = 'photo'

        elif message.video:

            file_id = message.video.file_id

            user_data['media_ids'].append(file_id)

            user_data['media_type'] = 'video'

        elif message.document:

            file_id = message.document.file_id

            user_data['media_ids'].append(file_id)

            user_data['media_type'] = 'document'

        

        text_length = len(user_data['text'].strip())

        

        if text_length < WERBUNG_SETTINGS['min_text_length']:

            all_messages = user_data['bot_messages'] + user_data['user_messages']

            await self._cleanup_messages(context, message.chat_id, all_messages)

            user_data['bot_messages'].clear()

            user_data['user_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                message.chat_id,

                f"📝 **Text zu kurz**\n\n"

                f"Mindestens {WERBUNG_SETTINGS['min_text_length']} Zeichen benötigt.\n"

                f"Aktuell: {text_length} Zeichen.\n\n"

                f"Sende mehr Text oder klicke 'Fertig'."

            )

            user_data['bot_messages'].append(msg.message_id)

            return self.WAITING_INPUT

        

        detected_buttons = self._extract_smart_buttons(user_data['text'])

        user_data['detected_buttons'] = detected_buttons

        

        all_messages = user_data['bot_messages'] + user_data['user_messages']

        await self._cleanup_messages(context, message.chat_id, all_messages)

        user_data['bot_messages'].clear()

        user_data['user_messages'].clear()

        

        button_info = ""

        if detected_buttons:

            button_info = f"\n{Emoji.LINK} **Buttons erkannt:** {len(detected_buttons)}\n"

            for btn in detected_buttons[:3]:

                button_info += f"  • {btn['text']}\n"

            if len(detected_buttons) > 3:

                button_info += f"  • ... und {len(detected_buttons) - 3} weitere\n"

        

        keyboard = [

            [

                InlineKeyboardButton(f"{Emoji.CHECK} Mit KI erstellen", callback_data="werbe_create"),

                InlineKeyboardButton("📝 Ohne KI", callback_data="werbe_skip_ai")

            ],

            [InlineKeyboardButton("➕ Manuellen Button hinzufügen", callback_data="werbe_add_manual_button")],

            [InlineKeyboardButton(f"{Emoji.CROSS} Abbrechen", callback_data="werbe_cancel")]

        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        msg = await self._send_message_safe(

            context,

            message.chat_id,

            f"{Emoji.CHECK} **Input erhalten!**\n\n"

            f"📝 Text: {text_length} Zeichen\n"

            f"{Emoji.IMAGE} Medien: {len(user_data['media_ids'])}\n"

            f"{button_info}\n"

            "Möchtest du mehr hinzufügen oder fertig?",

            reply_markup=reply_markup

        )

        

        user_data['bot_messages'].append(msg.message_id)

        

        return self.WAITING_INPUT

    

    async def add_manual_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Startet manuellen Button-Flow"""

        query = update.callback_query

        await query.answer()

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        all_messages = user_data['bot_messages'] + user_data['user_messages']

        await self._cleanup_messages(context, query.message.chat_id, all_messages)

        user_data['bot_messages'].clear()

        user_data['user_messages'].clear()

        

        msg = await self._send_message_safe(

            context,

            query.message.chat_id,

            f"➕ **Manuellen Button erstellen**\n\n"

            f"Schick mir den **Button-Text** (max 30 Zeichen):\n\n"

            f"Beispiele:\n"

            f"• 🛍️ Zum Shop\n"

            f"• 📞 Kontakt\n"

            f"• ℹ️ Mehr Infos"

        )

        user_data['bot_messages'].append(msg.message_id)

        

        return self.MANUAL_BUTTON_TEXT

    

    async def handle_manual_button_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Verarbeitet Button-Text"""

        user = update.effective_user

        message = update.message

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        user_data['user_messages'].append(message.message_id)

        

        button_text = message.text.strip()

        

        if len(button_text) > 30:

            await self._cleanup_messages(context, message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                message.chat_id,

                f"❌ **Text zu lang!**\n\n"

                f"Maximal 30 Zeichen erlaubt.\n"

                f"Aktuell: {len(button_text)} Zeichen.\n\n"

                f"Bitte sende einen kürzeren Text."

            )

            user_data['bot_messages'].append(msg.message_id)

            return self.MANUAL_BUTTON_TEXT

        

        user_data['temp_button_text'] = button_text

        

        all_messages = user_data['bot_messages'] + user_data['user_messages']

        await self._cleanup_messages(context, message.chat_id, all_messages)

        user_data['bot_messages'].clear()

        user_data['user_messages'].clear()

        

        msg = await self._send_message_safe(

            context,

            message.chat_id,

            f"✅ **Button-Text gespeichert:**\n\n"

            f"'{button_text}'\n\n"

            f"Jetzt schick mir die **URL** für den Button:\n\n"

            f"Beispiele:\n"

            f"• https://t.me/meinkanal\n"

            f"• https://example.com\n"

            f"• https://wa.me/491234567890"

        )

        user_data['bot_messages'].append(msg.message_id)

        

        return self.MANUAL_BUTTON_URL

    

    async def handle_manual_button_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Verarbeitet Button-URL"""

        user = update.effective_user

        message = update.message

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        user_data['user_messages'].append(message.message_id)

        

        url = message.text.strip()

        

        if not url.startswith(('http://', 'https://', 'viber://')):

            await self._cleanup_messages(context, message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                message.chat_id,

                f"❌ **Ungültige URL!**\n\n"

                f"Die URL muss mit http://, https:// oder viber:// beginnen.\n\n"

                f"Bitte sende eine gültige URL."

            )

            user_data['bot_messages'].append(msg.message_id)

            return self.MANUAL_BUTTON_URL

        

        manual_button = {

            'text': user_data['temp_button_text'],

            'url': url,

            'platform': 'manual'

        }

        user_data['manual_buttons'].append(manual_button)

        user_data['temp_button_text'] = None

        

        all_messages = user_data['bot_messages'] + user_data['user_messages']

        await self._cleanup_messages(context, message.chat_id, all_messages)

        user_data['bot_messages'].clear()

        user_data['user_messages'].clear()

        

        total_buttons = len(user_data.get('detected_buttons', [])) + len(user_data['manual_buttons'])

        

        keyboard = [

            [InlineKeyboardButton(f"{Emoji.CHECK} Fertig - Werbung erstellen", callback_data="werbe_create")],

            [InlineKeyboardButton("➕ Weiteren Button hinzufügen", callback_data="werbe_add_manual_button")],

            [InlineKeyboardButton(f"{Emoji.CROSS} Abbrechen", callback_data="werbe_cancel")]

        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        msg = await self._send_message_safe(

            context,

            message.chat_id,

            f"✅ **Button hinzugefügt!**\n\n"

            f"'{manual_button['text']}'\n"

            f"→ {url}\n\n"

            f"📝 Text: {len(user_data['text'].strip())} Zeichen\n"

            f"{Emoji.IMAGE} Medien: {len(user_data['media_ids'])}\n"

            f"{Emoji.LINK} Buttons gesamt: {total_buttons}\n\n"

            f"Möchtest du noch einen Button hinzufügen oder fertig?",

            reply_markup=reply_markup

        )

        user_data['bot_messages'].append(msg.message_id)

        

        return self.WAITING_INPUT

    

    async def skip_ai(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Überspringt KI und verwendet Original-Text direkt"""

        query = update.callback_query

        await query.answer("Verwende Original-Text...")

        

        user = query.from_user

        

        if user.id not in self.user_data_cache:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        user_data = self.user_data_cache[user.id]

        

        all_messages = user_data['bot_messages'] + user_data['user_messages']

        await self._cleanup_messages(context, query.message.chat_id, all_messages)

        user_data['bot_messages'].clear()

        user_data['user_messages'].clear()

        

        original_text = user_data['text'].strip()

        

        all_buttons = []

        all_buttons.extend(user_data.get('detected_buttons', []))

        all_buttons.extend(user_data.get('manual_buttons', []))

        

        user_data['gemini_result'] = {

            'title': 'Werbung',

            'content': original_text,

            'minimized_title': original_text[:50] + '...' if len(original_text) > 50 else original_text,

            'werbetyp': user_data['werbetyp'],

            'buttons': all_buttons

        }

        

        await self.show_preview(context, query.message.chat_id, user, user_data)

        

        return self.PREVIEW

    

    async def create_werbung(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Erstellt Werbung mit Gemini"""

        query = update.callback_query

        await query.answer()

        

        user = query.from_user

        

        if user.id not in self.user_data_cache:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        user_data = self.user_data_cache[user.id]

        

        all_messages = user_data['bot_messages'] + user_data['user_messages']

        await self._cleanup_messages(context, query.message.chat_id, all_messages)

        user_data['bot_messages'].clear()

        user_data['user_messages'].clear()

        

        processing_msg = await context.bot.send_message(

            chat_id=query.message.chat_id,

            text=f"{InfoMessages.GEMINI_WORKING}\n\n⏳ Einen Moment..."

        )

        

        gemini_result = create_werbung_with_gemini(

            user_text=user_data['text'],

            urls=user_data['urls'],

            media_count=len(user_data['media_ids']),

            werbetyp=user_data['werbetyp']

        )

        

        if not gemini_result:

            await processing_msg.edit_text(ErrorMessages.GEMINI_ERROR)

            return ConversationHandler.END

        

        all_buttons = []

        

        detected_buttons = user_data.get('detected_buttons', [])

        all_buttons.extend(detected_buttons)

        

        manual_buttons = user_data.get('manual_buttons', [])

        all_buttons.extend(manual_buttons)

        

        gemini_buttons_added = 0

        if gemini_result.get('buttons'):

            for gemini_btn in gemini_result['buttons']:

                if not any(btn['url'] == gemini_btn['url'] for btn in all_buttons):

                    all_buttons.append(gemini_btn)

                    gemini_buttons_added += 1

        

        gemini_result['buttons'] = all_buttons

        user_data['gemini_result'] = gemini_result

        

        await processing_msg.delete()

        

        await self.show_preview(context, query.message.chat_id, user, user_data)

        

        return self.PREVIEW

    

    async def show_preview(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user, user_data):

        """Zeigt Preview der Werbung"""

        gemini_result = user_data['gemini_result']

        

        title = gemini_result['title'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

        content = gemini_result['content'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

        

        preview_text = f"**{title}**\n\n{content}"

        

        if gemini_result['buttons']:

            preview_text += f"\n\n**Buttons:** ({len(gemini_result['buttons'])})\n"

            

            for btn in gemini_result['buttons'][:6]:

                btn_text = btn['text'].replace('_', '\\_').replace('*', '\\*')

                preview_text += f"• {btn_text}\n"

            

            if len(gemini_result['buttons']) > 6:

                preview_text += f"• ... und {len(gemini_result['buttons']) - 6} weitere\n"

        

        preview_prefix = f"{Emoji.PREVIEW} **Vorschau:**\n\n"

        max_caption_length = 1000

        

        if len(preview_prefix + preview_text) > max_caption_length:

            available_length = max_caption_length - len(preview_prefix) - 20

            preview_text = preview_text[:available_length] + "\n\n... (gekürzt)"

        

        keyboard = [

            [

                InlineKeyboardButton(f"{Emoji.CHECK} Passt - Posten", callback_data="werbe_post"),

                InlineKeyboardButton(f"{Emoji.REFRESH} Nochmal", callback_data="werbe_regenerate")

            ],

            [

                InlineKeyboardButton(f"{Emoji.CROSS} Abbrechen", callback_data="werbe_cancel")

            ]

        ]

        

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        try:

            if user_data['media_ids']:

                if user_data['media_type'] == 'video':

                    msg = await context.bot.send_video(

                        chat_id=chat_id,

                        video=user_data['media_ids'][0],

                        caption=f"{preview_prefix}{preview_text}",

                        reply_markup=reply_markup,

                        parse_mode='Markdown'

                    )

                else:

                    msg = await context.bot.send_photo(

                        chat_id=chat_id,

                        photo=user_data['media_ids'][0],

                        caption=f"{preview_prefix}{preview_text}",

                        reply_markup=reply_markup,

                        parse_mode='Markdown'

                    )

            else:

                msg = await self._send_message_safe(

                    context,

                    chat_id,

                    f"{preview_prefix}{preview_text}",

                    reply_markup=reply_markup

                )

        except BadRequest as e:

            logger.error(f"❌ Preview-Fehler: {e}")

            simple_preview = f"{Emoji.PREVIEW} Vorschau:\n\n{gemini_result['title']}\n\n{gemini_result['content'][:500]}"

            

            if user_data['media_ids']:

                if user_data['media_type'] == 'video':

                    msg = await context.bot.send_video(

                        chat_id=chat_id,

                        video=user_data['media_ids'][0],

                        caption=simple_preview,

                        reply_markup=reply_markup,

                        parse_mode=None

                    )

                else:

                    msg = await context.bot.send_photo(

                        chat_id=chat_id,

                        photo=user_data['media_ids'][0],

                        caption=simple_preview,

                        reply_markup=reply_markup,

                        parse_mode=None

                    )

            else:

                msg = await context.bot.send_message(

                    chat_id=chat_id,

                    text=simple_preview,

                    reply_markup=reply_markup,

                    parse_mode=None

                )

        

        user_data['bot_messages'].append(msg.message_id)

    

    async def regenerate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Regeneriert Werbung"""

        query = update.callback_query

        await query.answer("Erstelle neue Version...")

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        saved_buttons = user_data['gemini_result']['buttons']

        

        new_result = regenerate_werbung(

            previous_result=user_data['gemini_result'],

            user_text=user_data['text']

        )

        

        if not new_result:

            await query.answer("Fehler beim Regenerieren", show_alert=True)

            return self.PREVIEW

        

        new_result['buttons'] = saved_buttons

        user_data['gemini_result'] = new_result

        

        await self.show_preview(context, query.message.chat_id, user, user_data)

        

        return self.PREVIEW

    

    async def post_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Zeigt Posting-Einstellungen"""

        query = update.callback_query

        await query.answer()

        

        user = query.from_user

        

        if user.id not in self.user_data_cache:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        user_data = self.user_data_cache[user.id]

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        groups = get_active_groups()

        

        if not groups:

            keyboard = MenuSystem.create_main_menu_keyboard()

            msg = await self._send_message_safe(

                context,

                query.message.chat_id,

                f"⚠️ **Keine Gruppen verfügbar!**\n\n"

                f"Der Bot ist in keiner Gruppe.",

                reply_markup=keyboard

            )

            user_data['bot_messages'].append(msg.message_id)

            return ConversationHandler.END

        

        user_data['available_groups'] = groups

        

        keyboard = []

        selected_groups = user_data.get('selected_groups', [])

        

        for group in groups[:10]:

            group_emoji = "📢" if group['chat_type'] == 'channel' else "👥"

            admin_badge = " 👑" if group['bot_is_admin'] else ""

            check_mark = " ✅" if group['chat_id'] in selected_groups else ""

            button_text = f"{group_emoji} {group['title']}{admin_badge}{check_mark}"

            callback = f"werbe_select_group:{group['chat_id']}"

            

            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])

        

        if selected_groups:

            keyboard.append([

                InlineKeyboardButton(f"{Emoji.CHECK} Weiter zu Einstellungen", callback_data="werbe_groups_done")

            ])

        

        keyboard.append([

            InlineKeyboardButton(f"{Emoji.CROSS} Abbrechen", callback_data="werbe_cancel")

        ])

        

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        selected_count = len(selected_groups)

        selected_text = f"\n\n**Ausgewählt:** {selected_count} Gruppe(n)" if selected_count > 0 else ""

        

        msg = await self._send_message_safe(

            context,

            query.message.chat_id,

            f"📍 **Wähle die Zielgruppe(n):**\n\n"

            f"In welche Gruppen soll die Werbung gepostet werden?\n"

            f"(Mehrfachauswahl möglich)\n\n"

            f"👑 = Bot ist Administrator{selected_text}",

            reply_markup=reply_markup

        )

        

        user_data['bot_messages'].append(msg.message_id)

        

        return self.SETTINGS

    

    async def select_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """User hat Gruppe ausgewählt (Toggle)"""

        query = update.callback_query

        await query.answer()

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        try:

            chat_id = int(query.data.split(':')[1])

        except Exception as e:

            logger.error(f"❌ Fehler beim Parsen von chat_id: {e}")

            await query.answer("Ungültige Daten", show_alert=True)

            return self.SETTINGS

        

        selected_groups = user_data.get('selected_groups', [])

        if chat_id in selected_groups:

            selected_groups.remove(chat_id)

        else:

            selected_groups.append(chat_id)

        

        user_data['selected_groups'] = selected_groups

        

        await self._refresh_group_selection(context, query, user_data)

        

        return self.SETTINGS

    

    async def _refresh_group_selection(self, context: ContextTypes.DEFAULT_TYPE, query, user_data):

        """Aktualisiert die Gruppen-Auswahl Anzeige"""

        groups = user_data.get('available_groups', [])

        selected_groups = user_data.get('selected_groups', [])

        

        keyboard = []

        

        for group in groups[:10]:

            group_emoji = "📢" if group['chat_type'] == 'channel' else "👥"

            admin_badge = " 👑" if group['bot_is_admin'] else ""

            check_mark = " ✅" if group['chat_id'] in selected_groups else ""

            button_text = f"{group_emoji} {group['title']}{admin_badge}{check_mark}"

            callback = f"werbe_select_group:{group['chat_id']}"

            

            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])

        

        if selected_groups:

            keyboard.append([

                InlineKeyboardButton(f"{Emoji.CHECK} Weiter zu Einstellungen", callback_data="werbe_groups_done")

            ])

        

        keyboard.append([

            InlineKeyboardButton(f"{Emoji.CROSS} Abbrechen", callback_data="werbe_cancel")

        ])

        

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        selected_count = len(selected_groups)

        selected_text = f"\n\n**Ausgewählt:** {selected_count} Gruppe(n)" if selected_count > 0 else ""

        

        try:

            await query.message.edit_text(

                f"📍 **Wähle die Zielgruppe(n):**\n\n"

                f"In welche Gruppen soll die Werbung gepostet werden?\n"

                f"(Mehrfachauswahl möglich)\n\n"

                f"👑 = Bot ist Administrator{selected_text}",

                reply_markup=reply_markup,

                parse_mode='Markdown'

            )

        except Exception as e:

            logger.debug(f"Edit message failed: {e}")

    

    async def groups_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """User hat Gruppen-Auswahl bestätigt"""

        query = update.callback_query

        await query.answer()

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        selected_groups = user_data.get('selected_groups', [])

        

        if not selected_groups:

            await query.answer("Bitte wähle mindestens eine Gruppe!", show_alert=True)

            return self.SETTINGS

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        groups = user_data.get('available_groups', [])

        selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

        

        await self._show_settings_keyboard_multi(context, query, user_data, selected_group_names)

        

        return self.SETTINGS

    

    def _build_settings_keyboard(self, user_data):

        """Erstellt Settings-Keyboard"""

        current_intervall = user_data.get('intervall', IntervallTyp.EINMALIG)

        timer_seconds = user_data.get('expand_timer_seconds', 300)

        timer_minutes = timer_seconds // 60

        minutes = user_data.get('intervall_hours', 360)

        

        start_date = user_data.get('start_date')

        end_date = user_data.get('end_date')

        

        start_text = f"📅 Start: {start_date.strftime('%d.%m.%Y')}" if start_date else "📅 Start-Datum"

        end_text = f"📅 Ende: {end_date.strftime('%d.%m.%Y')}" if end_date else "📅 End-Datum"

        

        intervall_buttons = {

            IntervallTyp.EINMALIG: "Einmalig" + (" ✅" if current_intervall == IntervallTyp.EINMALIG else ""),

            IntervallTyp.STUENDLICH: f"Alle {minutes} Min" + (" ✅" if current_intervall == IntervallTyp.STUENDLICH else ""),

            IntervallTyp.TAEGLICH: "Täglich" + (" ✅" if current_intervall == IntervallTyp.TAEGLICH else ""),

            IntervallTyp.WOECHENTLICH: "Wöchentlich" + (" ✅" if current_intervall == IntervallTyp.WOECHENTLICH else "")

        }

        

        pin_text = f"{Emoji.PIN} Anheften: {'Ja ✅' if user_data.get('pin_enabled', False) else 'Nein'}"

        delete_text = f"{Emoji.DELETE} Alte löschen: {'Ja ✅' if user_data.get('delete_old', True) else 'Nein'}"

        timer_text = f"{Emoji.TIMER} Auto-Minimize: {timer_minutes} Min"

        

        keyboard = [

            [

                InlineKeyboardButton(start_text, callback_data="werbe_set_start_date"),

                InlineKeyboardButton(end_text, callback_data="werbe_set_end_date")

            ],

            [

                InlineKeyboardButton(intervall_buttons[IntervallTyp.EINMALIG], callback_data="werbe_interval:einmalig"),

                InlineKeyboardButton(intervall_buttons[IntervallTyp.STUENDLICH], callback_data="werbe_interval:stuendlich")

            ],

            [

                InlineKeyboardButton(intervall_buttons[IntervallTyp.TAEGLICH], callback_data="werbe_interval:taeglich"),

                InlineKeyboardButton(intervall_buttons[IntervallTyp.WOECHENTLICH], callback_data="werbe_interval:woechentlich")

            ],

            [

                InlineKeyboardButton(pin_text, callback_data="werbe_toggle_pin"),

                InlineKeyboardButton(delete_text, callback_data="werbe_toggle_delete")

            ],

            [

                InlineKeyboardButton(timer_text, callback_data="werbe_set_timer")

            ],

            [

                InlineKeyboardButton(f"{Emoji.CHECK} Jetzt posten", callback_data="werbe_confirm_post")

            ]

        ]

        

        return InlineKeyboardMarkup(keyboard)

    

    async def _show_settings_keyboard_multi(self, context: ContextTypes.DEFAULT_TYPE, query, user_data, selected_group_names):

        """Zeigt das Settings-Keyboard"""

        keyboard = self._build_settings_keyboard(user_data)

        

        groups_text = "\n".join([f"• {name}" for name in selected_group_names[:5]])

        if len(selected_group_names) > 5:

            groups_text += f"\n• ... und {len(selected_group_names) - 5} weitere"

        

        msg = await self._send_message_safe(

            context,

            query.message.chat_id,

            f"{InfoMessages.CHOOSE_OPTIONS}\n\n"

            f"**Zielgruppen:** ({len(selected_group_names)})\n"

            f"{groups_text}\n\n"

            f"**Einstellungen:**",

            reply_markup=keyboard

        )

        

        user_data['bot_messages'].append(msg.message_id)

    

    async def set_start_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Fragt nach Start-Datum"""

        query = update.callback_query

        await query.answer()

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        msg = await self._send_message_safe(

            context,

            query.message.chat_id,

            f"📅 **Start-Datum festlegen**\n\n"

            f"Ab wann soll die Werbung aktiv sein?\n\n"

            f"**Format:** DD.MM.YYYY\n\n"

            f"**Beispiele:**\n"

            f"• {datetime.now().strftime('%d.%m.%Y')} (heute)\n"

            f"• {(datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')} (morgen)\n"

            f"• {(datetime.now() + timedelta(days=7)).strftime('%d.%m.%Y')} (in 1 Woche)\n\n"

            f"Oder sende 'leer' um kein Start-Datum zu setzen."

        )

        user_data['bot_messages'].append(msg.message_id)

        

        return self.START_DATE_INPUT

    

    async def handle_start_date_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Verarbeitet Start-Datum"""

        user = update.effective_user

        message = update.message

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        user_data['user_messages'].append(message.message_id)

        

        date_str = message.text.strip().lower()

        

        if date_str == 'leer':

            user_data['start_date'] = None

            

            all_messages = user_data['bot_messages'] + user_data['user_messages']

            await self._cleanup_messages(context, message.chat_id, all_messages)

            user_data['bot_messages'].clear()

            user_data['user_messages'].clear()

            

            groups = user_data.get('available_groups', [])

            selected_groups = user_data.get('selected_groups', [])

            selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

            

            from types import SimpleNamespace

            pseudo_query = SimpleNamespace(message=message)

            await self._show_settings_keyboard_multi(context, pseudo_query, user_data, selected_group_names)

            

            return self.SETTINGS

        

        start_date = self._parse_date(date_str)

        

        if not start_date:

            await self._cleanup_messages(context, message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                message.chat_id,

                f"❌ **Ungültiges Datum!**\n\n"

                f"Bitte verwende das Format DD.MM.YYYY\n\n"

                f"Beispiel: {datetime.now().strftime('%d.%m.%Y')}"

            )

            user_data['bot_messages'].append(msg.message_id)

            return self.START_DATE_INPUT

        

        if start_date.date() < datetime.now().date():

            await self._cleanup_messages(context, message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                message.chat_id,

                f"❌ **Datum in der Vergangenheit!**\n\n"

                f"Das Start-Datum kann nicht in der Vergangenheit liegen.\n\n"

                f"Bitte wähle ein Datum ab heute: {datetime.now().strftime('%d.%m.%Y')}"

            )

            user_data['bot_messages'].append(msg.message_id)

            return self.START_DATE_INPUT

        

        user_data['start_date'] = start_date

        

        all_messages = user_data['bot_messages'] + user_data['user_messages']

        await self._cleanup_messages(context, message.chat_id, all_messages)

        user_data['bot_messages'].clear()

        user_data['user_messages'].clear()

        

        groups = user_data.get('available_groups', [])

        selected_groups = user_data.get('selected_groups', [])

        selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

        

        from types import SimpleNamespace

        pseudo_query = SimpleNamespace(message=message)

        await self._show_settings_keyboard_multi(context, pseudo_query, user_data, selected_group_names)

        

        return self.SETTINGS

    

    async def set_end_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Fragt nach End-Datum"""

        query = update.callback_query

        await query.answer()

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        msg = await self._send_message_safe(

            context,

            query.message.chat_id,

            f"📅 **End-Datum festlegen**\n\n"

            f"Bis wann soll die Werbung aktiv sein?\n\n"

            f"**Format:** DD.MM.YYYY\n\n"

            f"**Beispiele:**\n"

            f"• {(datetime.now() + timedelta(days=7)).strftime('%d.%m.%Y')} (in 1 Woche)\n"

            f"• {(datetime.now() + timedelta(days=30)).strftime('%d.%m.%Y')} (in 1 Monat)\n"

            f"• {(datetime.now() + timedelta(days=90)).strftime('%d.%m.%Y')} (in 3 Monaten)\n\n"

            f"Oder sende 'leer' um kein End-Datum zu setzen."

        )

        user_data['bot_messages'].append(msg.message_id)

        

        return self.END_DATE_INPUT

    

    async def handle_end_date_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Verarbeitet End-Datum"""

        user = update.effective_user

        message = update.message

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        user_data['user_messages'].append(message.message_id)

        

        date_str = message.text.strip().lower()

        

        if date_str == 'leer':

            user_data['end_date'] = None

            

            all_messages = user_data['bot_messages'] + user_data['user_messages']

            await self._cleanup_messages(context, message.chat_id, all_messages)

            user_data['bot_messages'].clear()

            user_data['user_messages'].clear()

            

            groups = user_data.get('available_groups', [])

            selected_groups = user_data.get('selected_groups', [])

            selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

            

            from types import SimpleNamespace

            pseudo_query = SimpleNamespace(message=message)

            await self._show_settings_keyboard_multi(context, pseudo_query, user_data, selected_group_names)

            

            return self.SETTINGS

        

        end_date = self._parse_date(date_str)

        

        if not end_date:

            await self._cleanup_messages(context, message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                message.chat_id,

                f"❌ **Ungültiges Datum!**\n\n"

                f"Bitte verwende das Format DD.MM.YYYY\n\n"

                f"Beispiel: {(datetime.now() + timedelta(days=7)).strftime('%d.%m.%Y')}"

            )

            user_data['bot_messages'].append(msg.message_id)

            return self.END_DATE_INPUT

        

        start_date = user_data.get('start_date')

        if start_date and end_date.date() <= start_date.date():

            await self._cleanup_messages(context, message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                message.chat_id,

                f"❌ **End-Datum muss nach Start-Datum liegen!**\n\n"

                f"Start-Datum: {start_date.strftime('%d.%m.%Y')}\n\n"

                f"Bitte wähle ein späteres Datum."

            )

            user_data['bot_messages'].append(msg.message_id)

            return self.END_DATE_INPUT

        

        if end_date.date() < datetime.now().date():

            await self._cleanup_messages(context, message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                message.chat_id,

                f"❌ **Datum in der Vergangenheit!**\n\n"

                f"Das End-Datum kann nicht in der Vergangenheit liegen."

            )

            user_data['bot_messages'].append(msg.message_id)

            return self.END_DATE_INPUT

        

        user_data['end_date'] = end_date

        

        all_messages = user_data['bot_messages'] + user_data['user_messages']

        await self._cleanup_messages(context, message.chat_id, all_messages)

        user_data['bot_messages'].clear()

        user_data['user_messages'].clear()

        

        groups = user_data.get('available_groups', [])

        selected_groups = user_data.get('selected_groups', [])

        selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

        

        from types import SimpleNamespace

        pseudo_query = SimpleNamespace(message=message)

        await self._show_settings_keyboard_multi(context, pseudo_query, user_data, selected_group_names)

        

        return self.SETTINGS

    

    async def set_interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Setzt Intervall-Einstellung"""

        query = update.callback_query

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        interval = query.data.split(':')[1]

        user_data['intervall'] = interval

        

        if interval == IntervallTyp.STUENDLICH:

            await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                query.message.chat_id,

                f"⏰ **Intervall in Minuten**\n\n"

                f"Alle wie viele Minuten soll die Werbung gepostet werden?\n\n"

                f"**Beispiele:**\n"

                f"• `30` = Alle 30 Minuten\n"

                f"• `60` = Alle 60 Minuten (1 Stunde)\n"

                f"• `120` = Alle 120 Minuten (2 Stunden)\n"

                f"• `360` = Alle 360 Minuten (6 Stunden)\n"

                f"• `720` = Alle 720 Minuten (12 Stunden)\n"

                f"• `1440` = Alle 1440 Minuten (24 Stunden)\n\n"

                f"Sende mir eine Zahl zwischen **1 und 1440 Minuten**:"

            )

            user_data['bot_messages'].append(msg.message_id)

            await query.answer()

            return self.MINUTES_INPUT

        

        elif interval == IntervallTyp.TAEGLICH:

            user_data['intervall_time'] = "12:00"

        elif interval == IntervallTyp.WOECHENTLICH:

            user_data['intervall_days'] = [1, 3, 5]

            user_data['intervall_time'] = "12:00"

        

        interval_text = {

            IntervallTyp.EINMALIG: "Einmalig",

            IntervallTyp.TAEGLICH: "Täglich (12:00)",

            IntervallTyp.WOECHENTLICH: "Wöchentlich (Mo/Mi/Fr)"

        }

        

        await query.answer(f"✅ {interval_text.get(interval, interval)}")

        

        selected_groups = user_data.get('selected_groups', [])

        

        if selected_groups:

            await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            groups = user_data.get('available_groups', [])

            selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

            await self._show_settings_keyboard_multi(context, query, user_data, selected_group_names)

        

        return self.SETTINGS

    

    async def handle_minutes_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Verarbeitet Minuten-Eingabe (1-1440 Min)"""

        user = update.effective_user

        message = update.message

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        user_data['user_messages'].append(message.message_id)

        

        try:

            minutes = int(message.text.strip())

            

            if minutes < 1 or minutes > 1440:

                await self._cleanup_messages(context, message.chat_id, user_data['bot_messages'])

                user_data['bot_messages'].clear()

                

                msg = await self._send_message_safe(

                    context,

                    message.chat_id,

                    f"❌ **Ungültiger Wert!**\n\n"

                    f"Bitte gib eine Zahl zwischen **1 und 1440 Minuten** ein.\n\n"

                    f"Du hast eingegeben: {minutes} Minuten"

                )

                user_data['bot_messages'].append(msg.message_id)

                return self.MINUTES_INPUT

            

            user_data['intervall_hours'] = minutes

            

            logger.info(f"✅ Intervall gesetzt: {minutes} Minuten")

            

            all_messages = user_data['bot_messages'] + user_data['user_messages']

            await self._cleanup_messages(context, message.chat_id, all_messages)

            user_data['bot_messages'].clear()

            user_data['user_messages'].clear()

            

            groups = user_data.get('available_groups', [])

            selected_groups = user_data.get('selected_groups', [])

            selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

            

            from types import SimpleNamespace

            pseudo_query = SimpleNamespace(message=message)

            await self._show_settings_keyboard_multi(context, pseudo_query, user_data, selected_group_names)

            

            return self.SETTINGS

            

        except ValueError:

            await self._cleanup_messages(context, message.chat_id, user_data['bot_messages'])

            user_data['bot_messages'].clear()

            

            msg = await self._send_message_safe(

                context,

                message.chat_id,

                f"❌ **Ungültige Eingabe!**\n\n"

                f"Bitte gib eine ganze Zahl zwischen **1 und 1440 Minuten** ein."

            )

            user_data['bot_messages'].append(msg.message_id)

            return self.MINUTES_INPUT

    

    async def set_timer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Zeigt Timer-Auswahl"""

        query = update.callback_query

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        keyboard = [

            [

                InlineKeyboardButton("30 Sek", callback_data="werbe_timer:30"),

                InlineKeyboardButton("1 Min", callback_data="werbe_timer:60")

            ],

            [

                InlineKeyboardButton("2 Min", callback_data="werbe_timer:120"),

                InlineKeyboardButton("5 Min", callback_data="werbe_timer:300")

            ],

            [

                InlineKeyboardButton("10 Min", callback_data="werbe_timer:600"),

                InlineKeyboardButton("30 Min", callback_data="werbe_timer:1800")

            ],

            [

                InlineKeyboardButton(f"{Emoji.BACK} Zurück", callback_data="werbe_timer_back")

            ]

        ]

        

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        msg = await self._send_message_safe(

            context,

            query.message.chat_id,

            f"{Emoji.TIMER} **Auto-Minimize Timer**\n\n"

            f"Nach wie vielen Sekunden/Minuten soll sich die expandierte Werbung automatisch minimieren?\n\n"

            f"**Aktuell:** {user_data.get('expand_timer_seconds', 300) // 60} Minuten",

            reply_markup=reply_markup

        )

        

        user_data['bot_messages'].append(msg.message_id)

        

        await query.answer()

        return self.SETTINGS

    

    async def set_timer_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Setzt Timer-Wert"""

        query = update.callback_query

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        timer_seconds = int(query.data.split(':')[1])

        user_data['expand_timer_seconds'] = timer_seconds

        

        timer_text = f"{timer_seconds} Sek" if timer_seconds < 60 else f"{timer_seconds // 60} Min"

        await query.answer(f"✅ Timer: {timer_text}")

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        selected_groups = user_data.get('selected_groups', [])

        groups = user_data.get('available_groups', [])

        selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

        

        if selected_group_names:

            await self._show_settings_keyboard_multi(context, query, user_data, selected_group_names)

        

        return self.SETTINGS

    

    async def timer_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Zurück von Timer-Auswahl"""

        query = update.callback_query

        await query.answer()

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        selected_groups = user_data.get('selected_groups', [])

        groups = user_data.get('available_groups', [])

        selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

        

        if selected_group_names:

            await self._show_settings_keyboard_multi(context, query, user_data, selected_group_names)

        

        return self.SETTINGS

    

    async def toggle_pin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Toggle Pin-Einstellung"""

        query = update.callback_query

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        current = user_data.get('pin_enabled', False)

        user_data['pin_enabled'] = not current

        

        await query.answer(f"📌 Anheften: {'Ja' if user_data['pin_enabled'] else 'Nein'}")

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        selected_groups = user_data.get('selected_groups', [])

        groups = user_data.get('available_groups', [])

        selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

        

        if selected_group_names:

            await self._show_settings_keyboard_multi(context, query, user_data, selected_group_names)

        

        return self.SETTINGS

    

    async def toggle_delete_old(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Toggle Delete-Old-Einstellung"""

        query = update.callback_query

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        current = user_data.get('delete_old', True)

        user_data['delete_old'] = not current

        

        await query.answer(f"🗑️ Alte löschen: {'Ja' if user_data['delete_old'] else 'Nein'}")

        

        await self._cleanup_messages(context, query.message.chat_id, user_data['bot_messages'])

        user_data['bot_messages'].clear()

        

        selected_groups = user_data.get('selected_groups', [])

        groups = user_data.get('available_groups', [])

        selected_group_names = [g['title'] for g in groups if g['chat_id'] in selected_groups]

        

        if selected_group_names:

            await self._show_settings_keyboard_multi(context, query, user_data, selected_group_names)

        

        return self.SETTINGS

    

    async def confirm_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Postet die Werbung final"""

        query = update.callback_query

        await query.answer("Wird gepostet...")

        

        user = query.from_user

        user_data = self.user_data_cache.get(user.id)

        

        if not user_data:

            keyboard = MenuSystem.create_main_menu_keyboard()

            await query.message.reply_text("Session abgelaufen.", reply_markup=keyboard)

            return ConversationHandler.END

        

        selected_groups = user_data.get('selected_groups', [])

        

        if not selected_groups:

            await query.answer("Bitte wähle zuerst eine Zielgruppe!", show_alert=True)

            return self.SETTINGS

        

        gemini_result = user_data['gemini_result']

        delete_old = user_data.get('delete_old', True)

        

        all_messages = user_data['bot_messages'] + user_data['user_messages']

        await self._cleanup_messages(context, query.message.chat_id, all_messages)

        

        success_count = 0

        failed_groups = []

        

        logger.info(f"🚀 Starte Posting in {len(selected_groups)} Gruppe(n)")

        

        for target_chat_id in selected_groups:

            try:

                logger.info(f"📤 Verarbeite Gruppe: Chat ID={target_chat_id}")

                

                werbung_id = WerbungDB.create(

                    user_id=user.id,

                    title=gemini_result['title'],

                    content=gemini_result['content'],

                    werbetyp=gemini_result['werbetyp'],

                    media_ids=user_data['media_ids'],

                    media_type=user_data['media_type'],

                    buttons=gemini_result['buttons'],

                    intervall=user_data.get('intervall', IntervallTyp.EINMALIG),

                    intervall_hours=user_data.get('intervall_hours'),

                    intervall_time=user_data.get('intervall_time'),

                    intervall_days=user_data.get('intervall_days'),

                    pin_enabled=user_data.get('pin_enabled', False),

                    delete_old=delete_old,

                    minimized_title=gemini_result['minimized_title'],

                    target_chat_id=target_chat_id,

                    expand_timer_seconds=user_data.get('expand_timer_seconds', 300),

                    start_date=user_data.get('start_date'),

                    end_date=user_data.get('end_date')

                )

                

                logger.info(f"✅ Werbung {werbung_id} in DB erstellt")

                

                WerbungDB.activate(werbung_id)

                ActionLogModel.log(user.id, 'werbe_created', {'werbung_id': werbung_id}, True)

                

                logger.info(f"📤 Poste Werbung {werbung_id} in Chat {target_chat_id}")

                

                try:

                    message_id = await post_minimized_ad(context.bot, werbung_id, target_chat_id)

                except BadRequest as post_error:

                    if "can't parse entities" in str(post_error).lower():

                        logger.error(f"❌ Markdown-Parse-Error beim Posten: {post_error}")

                    else:

                        logger.error(f"❌ BadRequest beim Posten: {post_error}")

                    message_id = None

                except Exception as post_error:

                    logger.error(f"❌ Exception beim Posten: {post_error}", exc_info=True)

                    message_id = None

                

                if message_id:

                    logger.info(f"✅ Werbung gepostet: Message {message_id} in Chat {target_chat_id}")

                    success_count += 1

                    

                    try:

                        WerbungDB.update_last_posted(werbung_id)

                        logger.info(f"✅ last_posted_at gesetzt für Werbung {werbung_id}")

                    except Exception as e:

                        logger.error(f"❌ Fehler beim Setzen von last_posted_at: {e}")

                    

                    if user_data.get('intervall', IntervallTyp.EINMALIG) != IntervallTyp.EINMALIG:

                        scheduler = get_scheduler()

                        if scheduler:

                            try:

                                scheduler.schedule_werbung(werbung_id)

                                logger.info(f"⏰ Intervall-Job für Werbung {werbung_id} im Scheduler geplant")

                            except Exception as e:

                                logger.error(f"❌ Fehler beim Planen des Scheduler-Jobs: {e}", exc_info=True)

                        else:

                            logger.warning(f"⚠️ Scheduler nicht verfügbar")

                else:

                    logger.error(f"❌ post_minimized_ad gab None zurück für Chat {target_chat_id}")

                    groups = user_data.get('available_groups', [])

                    group = next((g for g in groups if g['chat_id'] == target_chat_id), None)

                    group_name = group['title'] if group else f"Chat {target_chat_id}"

                    failed_groups.append(f"{group_name} (Posting fehlgeschlagen)")

                    

            except Forbidden as e:

                logger.error(f"❌ Bot wurde aus Gruppe geblockt: Chat {target_chat_id}: {e}")

                groups = user_data.get('available_groups', [])

                group = next((g for g in groups if g['chat_id'] == target_chat_id), None)

                group_name = group['title'] if group else f"Chat {target_chat_id}"

                failed_groups.append(f"{group_name} (Bot entfernt)")

                

            except BadRequest as e:

                logger.error(f"❌ BadRequest beim Posten in Chat {target_chat_id}: {e}")

                groups = user_data.get('available_groups', [])

                group = next((g for g in groups if g['chat_id'] == target_chat_id), None)

                group_name = group['title'] if group else f"Chat {target_chat_id}"

                failed_groups.append(f"{group_name} (Keine Berechtigung)")

                

            except NetworkError as e:

                logger.error(f"❌ Netzwerkfehler beim Posten in Chat {target_chat_id}: {e}")

                groups = user_data.get('available_groups', [])

                group = next((g for g in groups if g['chat_id'] == target_chat_id), None)

                group_name = group['title'] if group else f"Chat {target_chat_id}"

                failed_groups.append(f"{group_name} (Netzwerkfehler)")

                

            except Exception as e:

                logger.error(f"❌ Unerwarteter Fehler beim Posten in Chat {target_chat_id}: {e}", exc_info=True)

                groups = user_data.get('available_groups', [])

                group = next((g for g in groups if g['chat_id'] == target_chat_id), None)

                group_name = group['title'] if group else f"Chat {target_chat_id}"

                failed_groups.append(f"{group_name} ({str(e)[:50]})")

        

        keyboard = MenuSystem.create_main_menu_keyboard()

        timer_min = user_data.get('expand_timer_seconds', 300) // 60

        

        if success_count == len(selected_groups):

            await context.bot.send_message(

                chat_id=user.id,

                text=f"{Emoji.CHECK} {SuccessMessages.WERBUNG_POSTED}\n\n"

                     f"Die Werbung wurde in {success_count} Gruppe(n) erfolgreich gepostet!\n\n"

                     f"{Emoji.TIMER} Auto-Minimize: {timer_min} Min\n"

                     f"{Emoji.LINK} Buttons: {len(gemini_result['buttons'])}",

                reply_markup=keyboard

            )

        elif success_count > 0:

            failed_text = "\n".join([f"• {name}" for name in failed_groups[:10]])

            if len(failed_groups) > 10:

                failed_text += f"\n• ... und {len(failed_groups) - 10} weitere"

                

            await context.bot.send_message(

                chat_id=user.id,

                text=f"⚠️ **Teilweise erfolgreich**\n\n"

                     f"✅ Erfolgreich: {success_count} Gruppe(n)\n"

                     f"❌ Fehlgeschlagen ({len(failed_groups)}):\n{failed_text}\n\n"

                     f"**Mögliche Gründe:**\n"

                     f"• Bot wurde aus Gruppe entfernt\n"

                     f"• Bot hat keine Schreibrechte\n"

                     f"• Gruppe existiert nicht mehr",

                reply_markup=keyboard,

                parse_mode='Markdown'

            )

        else:

            failed_text = "\n".join([f"• {name}" for name in failed_groups[:10]])

            if len(failed_groups) > 10:

                failed_text += f"\n• ... und {len(failed_groups) - 10} weitere"

                

            await context.bot.send_message(

                chat_id=user.id,

                text=f"❌ **Fehler beim Posten**\n\n"

                     f"Die Werbung konnte in keiner Gruppe gepostet werden.\n\n"

                     f"**Fehlgeschlagene Gruppen:**\n{failed_text}",

                reply_markup=keyboard,

                parse_mode='Markdown'

            )

        

        if user.id in self.user_data_cache:

            del self.user_data_cache[user.id]

        

        return ConversationHandler.END

    

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Bricht Werbungs-Erstellung ab"""

        query = update.callback_query

        await query.answer("Abgebrochen")

        

        user = query.from_user

        

        if user.id in self.user_data_cache:

            user_data = self.user_data_cache[user.id]

            

            all_messages = user_data.get('bot_messages', []) + user_data.get('user_messages', [])

            await self._cleanup_messages(context, query.message.chat_id, all_messages)

            

            del self.user_data_cache[user.id]

        

        keyboard = MenuSystem.create_main_menu_keyboard()

        await self._send_message_safe(

            context,

            query.message.chat_id,

            f"{Emoji.CROSS} Werbungs-Erstellung abgebrochen.",

            reply_markup=keyboard

        )

        return ConversationHandler.END

    

    async def handle_expand(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Callback: Expandiert minimierte Werbung"""

        query = update.callback_query

        

        try:

            data = query.data.split(':')

            if len(data) != 2:

                await query.answer("Ungültige Daten", show_alert=True)

                return

            

            werbung_id = int(data[1])

            success = await expand_ad(update, context, werbung_id)

            

            if success:

                await query.answer(f"{Emoji.CHECK} Werbung wird angezeigt")

            else:

                await query.answer("Fehler beim Laden", show_alert=True)

                

        except Exception as e:

            logger.error(f"❌ Fehler in handle_expand: {e}", exc_info=True)

            await query.answer("❌ Fehler", show_alert=True)

    

    async def handle_minimize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Callback: Minimiert expandierte Werbung"""

        query = update.callback_query

        

        try:

            data = query.data.split(':')

            if len(data) != 2:

                await query.answer("Ungültige Daten", show_alert=True)

                return

            

            werbung_id = int(data[1])

            result = await minimize_ad(update, context, werbung_id)

            

            if result is None:

                await query.answer("❌ Interner Fehler", show_alert=True)

                return

            

            success, message = result

            

            if success:

                await query.answer(f"✅ {message}")

            else:

                await query.answer(f"❌ {message}", show_alert=True)

                

        except Exception as e:

            logger.error(f"❌ Fehler in handle_minimize: {e}", exc_info=True)

            await query.answer("❌ Fehler", show_alert=True)

    

    # ========== WVERWALTEN EDIT HANDLERS ==========

    

    async def handle_wverwalten_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Zeigt Details einer Werbung zur Bearbeitung"""

        query = update.callback_query

        await query.answer()

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        await self._show_wverwalten_edit_view(query, werbung)

    

    async def _show_wverwalten_edit_view(self, query, werbung):

        """Helper: Zeigt Edit-Ansicht für Werbung"""

        werbung_id = werbung['id']

        status_text = "✅ Aktiv" if werbung['is_active'] else "⏸️ Pausiert"

        pin_status = "✅" if werbung.get('pin_enabled', False) else "❌"

        delete_status = "✅" if werbung.get('delete_old', True) else "❌"

        

        minutes = werbung.get('intervall_hours', 0)

        intervall_text = f"Alle {minutes} Min" if werbung.get('intervall') == IntervallTyp.STUENDLICH else werbung.get('intervall', 'einmalig')

        

        media_text = "🖼️" if werbung.get('media_type') == 'photo' else "🎥" if werbung.get('media_type') == 'video' else "📄"

        media_status = f"{media_text} Ja" if werbung.get('media_ids') else "❌ Nein"

        

        text = (

            f"📋 **Werbung bearbeiten**\n\n"

            f"**Titel:** {werbung['title']}\n\n"

            f"**Status:** {status_text}\n"

            f"**Posts:** {werbung.get('total_posts', 0)}\n"

            f"**Expands:** {werbung.get('total_expands', 0)}\n"

            f"**Intervall:** {intervall_text}\n"

            f"**Pin:** {pin_status} | **Alte löschen:** {delete_status}\n"

            f"**Media:** {media_status}\n\n"

            f"**Inhalt:**\n{werbung['content'][:200]}"

        )

        

        if len(werbung['content']) > 200:

            text += "..."

        

        keyboard = [

            [

                InlineKeyboardButton("👥 Gruppen", callback_data=f"wverwalten_groups:{werbung_id}"),

                InlineKeyboardButton("✏️ Text", callback_data=f"wverwalten_text:{werbung_id}")

            ],

            [

                InlineKeyboardButton("📸 Media", callback_data=f"wverwalten_media:{werbung_id}"),

                InlineKeyboardButton("⏱️ Intervall", callback_data=f"wverwalten_interval:{werbung_id}")

            ],

            [

                InlineKeyboardButton(f"🗑️ Alte löschen: {delete_status}", callback_data=f"wverwalten_toggle_delete:{werbung_id}")

            ],

            []

        ]

        

        if werbung['is_active']:

            keyboard[3].append(InlineKeyboardButton("⏸️ Pausieren", callback_data=f"wverwalten_pause:{werbung_id}"))

        else:

            keyboard[3].append(InlineKeyboardButton("▶️ Aktivieren", callback_data=f"wverwalten_activate:{werbung_id}"))

        

        keyboard.append([InlineKeyboardButton("🗑️ Werbung löschen", callback_data=f"wverwalten_delete_confirm:{werbung_id}")])

        keyboard.append([InlineKeyboardButton("◀️ Zurück zur Liste", callback_data="wverwalten_back")])

        

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        try:

            await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

        except BadRequest as e:

            logger.warning(f"Konnte Message nicht editieren: {e}")

            try:

                await query.message.delete()

            except:

                pass

            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    

    async def handle_wverwalten_toggle_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Toggle Delete-Old für diese EINE Werbung"""

        query = update.callback_query

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        current = werbung.get('delete_old', True)

        new_value = not current

        

        WerbungDB.update_delete_old(werbung_id, new_value)

        

        await query.answer(f"✅ Alte löschen: {'Ja' if new_value else 'Nein'}", show_alert=False)

        

        werbung = WerbungDB.get_by_id(werbung_id)

        await self._show_wverwalten_edit_view(query, werbung)

    

    async def handle_wverwalten_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Pausiert eine Werbung"""

        query = update.callback_query

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        WerbungDB.deactivate(werbung_id)

        

        scheduler = get_scheduler()

        if scheduler:

            try:

                scheduler.remove_werbung_job(werbung_id)

                logger.info(f"⏸️ Job für Werbung {werbung_id} aus Scheduler entfernt")

            except Exception as e:

                logger.warning(f"⚠️ Fehler beim Entfernen des Jobs: {e}")

        

        await query.answer("✅ Werbung pausiert", show_alert=False)

        

        werbung = WerbungDB.get_by_id(werbung_id)

        await self._show_wverwalten_edit_view(query, werbung)

    

    async def handle_wverwalten_activate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Aktiviert eine Werbung"""

        query = update.callback_query

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        WerbungDB.activate(werbung_id)

        

        if werbung.get('intervall') != IntervallTyp.EINMALIG:

            scheduler = get_scheduler()

            if scheduler:

                try:

                    scheduler.schedule_werbung(werbung_id)

                    logger.info(f"▶️ Job für Werbung {werbung_id} im Scheduler geplant")

                except Exception as e:

                    logger.error(f"❌ Fehler beim Planen des Jobs: {e}", exc_info=True)

        

        await query.answer("✅ Werbung aktiviert", show_alert=False)

        

        werbung = WerbungDB.get_by_id(werbung_id)

        await self._show_wverwalten_edit_view(query, werbung)

    

    async def handle_wverwalten_delete_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Zeigt Lösch-Bestätigung"""

        query = update.callback_query

        await query.answer()

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        keyboard = [

            [

                InlineKeyboardButton("✅ Ja, löschen!", callback_data=f"wverwalten_delete:{werbung_id}"),

                InlineKeyboardButton("❌ Abbrechen", callback_data=f"wverwalten_edit:{werbung_id}")

            ]

        ]

        

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        try:

            await query.message.edit_text(

                f"⚠️ **Werbung wirklich löschen?**\n\n"

                f"**Titel:** {werbung['title']}\n\n"

                f"Die Werbung wird dauerhaft gelöscht!\n"

                f"Diese Aktion kann nicht rückgängig gemacht werden.",

                reply_markup=reply_markup,

                parse_mode='Markdown'

            )

        except BadRequest:

            await context.bot.send_message(

                chat_id=query.message.chat_id,

                text=f"⚠️ **Werbung wirklich löschen?**\n\n"

                     f"**Titel:** {werbung['title']}\n\n"

                     f"Die Werbung wird dauerhaft gelöscht!",

                reply_markup=reply_markup,

                parse_mode='Markdown'

            )

    

    async def handle_wverwalten_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Löscht eine Werbung"""

        query = update.callback_query

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        werbung_title = werbung['title']

        

        scheduler = get_scheduler()

        if scheduler:

            try:

                scheduler.remove_werbung_job(werbung_id)

                logger.info(f"🗑️ Job für Werbung {werbung_id} aus Scheduler entfernt")

            except Exception as e:

                logger.debug(f"Job bereits entfernt: {e}")

        

        success = WerbungDB.delete(werbung_id)

        

        if success:

            await query.answer("✅ Werbung gelöscht!", show_alert=False)

            

            try:

                await query.message.delete()

            except:

                pass

            

            keyboard = MenuSystem.create_admin_menu_keyboard()

            await context.bot.send_message(

                chat_id=query.message.chat_id,

                text=f"✅ **Werbung gelöscht!**\n\n"

                     f"Die Werbung **{werbung_title}** wurde erfolgreich gelöscht.",

                reply_markup=keyboard,

                parse_mode='Markdown'

            )

            

            logger.info(f"✅ Werbung {werbung_id} von User {update.effective_user.id} gelöscht")

        else:

            await query.answer("❌ Fehler beim Löschen", show_alert=True)

    

    async def handle_wverwalten_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Zurück zur Werbungsliste"""

        query = update.callback_query

        await query.answer()

        

        try:

            await query.message.delete()

        except:

            pass

        

        await MenuSystem.show_wverwalten(update, context)

    

    # ========== GRUPPEN ÄNDERN (NEU: MIT MEHRFACHAUSWAHL + KOPIE-FUNKTION) ==========

    

    async def handle_wverwalten_change_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Ändert Zielgruppe für bestehende Werbung - MIT MEHRFACHAUSWAHL"""

        query = update.callback_query

        await query.answer()

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        groups = get_active_groups()

        

        if not groups:

            await query.answer("Keine Gruppen verfügbar", show_alert=True)

            return

        

        current_chat_id = werbung.get('target_chat_id')

        

        # State in context.user_data speichern

        context.user_data['editing_werbung_id'] = werbung_id

        context.user_data['original_chat_id'] = current_chat_id

        context.user_data['selected_group_ids'] = []  # Neu ausgewählte Gruppen

        context.user_data['available_groups'] = groups

        

        # Finde aktuellen Gruppennamen

        current_group_name = "Unbekannt"

        for g in groups:

            if g['chat_id'] == current_chat_id:

                current_group_name = g['title']

                break

        

        keyboard = []

        for group in groups[:10]:

            group_emoji = "📢" if group['chat_type'] == 'channel' else "👥"

            is_current = " 🔵" if group['chat_id'] == current_chat_id else ""

            button_text = f"{group_emoji} {group['title']}{is_current}"

            callback = f"wverwalten_toggle_group:{group['chat_id']}"

            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])

        

        keyboard.append([InlineKeyboardButton("✅ Auswahl bestätigen", callback_data="wverwalten_groups_confirm")])

        keyboard.append([InlineKeyboardButton("◀️ Zurück", callback_data=f"wverwalten_edit:{werbung_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        try:

            await query.message.edit_text(

                f"👥 **Gruppen ändern**\n\n"

                f"**Werbung:** {werbung['title'][:30]}...\n\n"

                f"**Aktuelle Gruppe:** 🔵\n{current_group_name}\n\n"

                f"━━━━━━━━━━━━━━━━\n\n"

                f"💡 **Mehrfachauswahl möglich:**\n"

                f"• Wähle EINE Gruppe → Werbung wird in diese Gruppe verschoben\n"

                f"• Wähle MEHRERE Gruppen → Werbung wird kopiert\n\n"

                f"Klicke auf Gruppen um sie auszuwählen:",

                reply_markup=reply_markup,

                parse_mode='Markdown'

            )

        except BadRequest as e:

            logger.warning(f"Edit failed: {e}")

    

    async def handle_wverwalten_toggle_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Toggle Gruppen-Auswahl"""

        query = update.callback_query

        

        try:

            chat_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Daten", show_alert=True)

            return

        

        werbung_id = context.user_data.get('editing_werbung_id')

        original_chat_id = context.user_data.get('original_chat_id')

        selected_groups = context.user_data.get('selected_group_ids', [])

        

        if not werbung_id or original_chat_id is None:

            await query.answer("Session abgelaufen", show_alert=True)

            return

        

        # Toggle

        if chat_id in selected_groups:

            selected_groups.remove(chat_id)

        else:

            selected_groups.append(chat_id)

        

        context.user_data['selected_group_ids'] = selected_groups

        

        # Aktualisiere Ansicht

        werbung = WerbungDB.get_by_id(werbung_id)

        groups = context.user_data.get('available_groups', [])

        

        current_group_name = "Unbekannt"

        for g in groups:

            if g['chat_id'] == original_chat_id:

                current_group_name = g['title']

                break

        

        keyboard = []

        for group in groups[:10]:

            group_emoji = "📢" if group['chat_type'] == 'channel' else "👥"

            is_current = " 🔵" if group['chat_id'] == original_chat_id else ""

            is_selected = " ✅" if group['chat_id'] in selected_groups else ""

            button_text = f"{group_emoji} {group['title']}{is_current}{is_selected}"

            callback = f"wverwalten_toggle_group:{group['chat_id']}"

            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])

        

        selected_text = ""

        if selected_groups:

            selected_text = f"\n\n**Ausgewählt:** {len(selected_groups)} Gruppe(n)"

        

        keyboard.append([InlineKeyboardButton("✅ Auswahl bestätigen", callback_data="wverwalten_groups_confirm")])

        keyboard.append([InlineKeyboardButton("◀️ Zurück", callback_data=f"wverwalten_edit:{werbung_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        try:

            await query.message.edit_text(

                f"👥 **Gruppen ändern**\n\n"

                f"**Werbung:** {werbung['title'][:30]}...\n\n"

                f"**Aktuelle Gruppe:** 🔵\n{current_group_name}\n\n"

                f"━━━━━━━━━━━━━━━━\n\n"

                f"💡 **Mehrfachauswahl möglich:**\n"

                f"• Wähle EINE Gruppe → Werbung wird verschoben\n"

                f"• Wähle MEHRERE Gruppen → Werbung wird kopiert{selected_text}\n\n"

                f"Klicke auf Gruppen um sie auszuwählen:",

                reply_markup=reply_markup,

                parse_mode='Markdown'

            )

            await query.answer()

        except BadRequest as e:

            logger.warning(f"Edit failed: {e}")

            await query.answer()

    

    async def handle_wverwalten_groups_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Bestätigt Gruppen-Auswahl und verschiebt/kopiert Werbung"""

        query = update.callback_query

        

        werbung_id = context.user_data.get('editing_werbung_id')

        original_chat_id = context.user_data.get('original_chat_id')

        selected_groups = context.user_data.get('selected_group_ids', [])

        

        if not werbung_id or original_chat_id is None:

            await query.answer("Session abgelaufen", show_alert=True)

            return

        

        if not selected_groups:

            await query.answer("Bitte wähle mindestens eine Gruppe!", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        groups = context.user_data.get('available_groups', [])

        

        try:

            if len(selected_groups) == 1:

                # NUR EINE Gruppe: Verschieben

                new_chat_id = selected_groups[0]

                WerbungDB.update(werbung_id, target_chat_id=new_chat_id)

                

                group_name = next((g['title'] for g in groups if g['chat_id'] == new_chat_id), f"Chat {new_chat_id}")

                await query.answer(f"✅ Werbung verschoben nach: {group_name}", show_alert=False)

                

            else:

                # MEHRERE Gruppen: Kopieren

                copied_count = 0

                for new_chat_id in selected_groups:

                    if new_chat_id == original_chat_id:

                        continue  # Original behalten

                    

                    # Kopie erstellen

                    new_id = WerbungDB.create(

                        user_id=werbung['user_id'],

                        title=werbung['title'],

                        content=werbung['content'],

                        werbetyp=werbung['werbetyp'],

                        media_ids=werbung.get('media_ids', []),

                        media_type=werbung.get('media_type'),

                        buttons=werbung.get('buttons', []),

                        intervall=werbung.get('intervall', IntervallTyp.EINMALIG),

                        intervall_hours=werbung.get('intervall_hours'),

                        intervall_time=werbung.get('intervall_time'),

                        intervall_days=werbung.get('intervall_days'),

                        pin_enabled=werbung.get('pin_enabled', False),

                        delete_old=werbung.get('delete_old', True),

                        minimized_title=werbung.get('minimized_title', ''),

                        target_chat_id=new_chat_id,

                        expand_timer_seconds=werbung.get('expand_timer_seconds', 300),

                        start_date=werbung.get('start_date'),

                        end_date=werbung.get('end_date')

                    )

                    

                    if new_id:

                        WerbungDB.activate(new_id)

                        copied_count += 1

                        

                        # Scheduler-Job wenn nötig

                        if werbung.get('intervall') != IntervallTyp.EINMALIG and werbung.get('is_active'):

                            scheduler = get_scheduler()

                            if scheduler:

                                try:

                                    scheduler.schedule_werbung(new_id)

                                except Exception as e:

                                    logger.error(f"Scheduler-Fehler: {e}")

                

                await query.answer(f"✅ Werbung in {copied_count} Gruppe(n) kopiert!", show_alert=True)

            

            # Cleanup

            context.user_data.pop('editing_werbung_id', None)

            context.user_data.pop('original_chat_id', None)

            context.user_data.pop('selected_group_ids', None)

            context.user_data.pop('available_groups', None)

            

            # Zurück zur Edit-Ansicht

            werbung = WerbungDB.get_by_id(werbung_id)

            await self._show_wverwalten_edit_view(query, werbung)

            

        except Exception as e:

            logger.error(f"Fehler beim Gruppen-Update: {e}", exc_info=True)

            await query.answer("❌ Fehler beim Speichern", show_alert=True)

    

    # ========== TEXT ÄNDERN ==========

    

    async def handle_wverwalten_edit_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Startet Text-Bearbeitung"""

        query = update.callback_query

        await query.answer()

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        # State in context.user_data speichern

        context.user_data['editing_werbung_id'] = werbung_id

        context.user_data['waiting_for_text'] = True

        

        try:

            await query.message.delete()

        except:

            pass

        

        await query.message.reply_text(

            f"✏️ **Text bearbeiten**\n\n"

            f"**Aktueller Text:**\n{werbung['content'][:500]}\n\n"

            f"Sende mir den **neuen Text**:\n"

            f"(Du kannst Markdown verwenden: **fett**, __unterstrichen__, *kursiv*)",

            parse_mode='Markdown'

        )

    

    async def handle_wverwalten_edit_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Verarbeitet neuen Text"""

        user = update.effective_user

        message = update.message

        

        # Prüfe ob wir auf Text warten

        if not context.user_data.get('waiting_for_text'):

            return

        

        werbung_id = context.user_data.get('editing_werbung_id')

        

        if not werbung_id:

            await message.reply_text("❌ Session abgelaufen. Bitte versuche es erneut.")

            context.user_data.clear()

            return

        

        new_text = message.text.strip()

        

        if len(new_text) < 10:

            await message.reply_text("❌ Text zu kurz (min. 10 Zeichen). Bitte erneut versuchen:")

            return

        

        # Update in DB

        success = WerbungDB.update(werbung_id, content=new_text)

        

        # Cleanup State

        context.user_data.pop('waiting_for_text', None)

        context.user_data.pop('editing_werbung_id', None)

        

        try:

            await message.delete()

        except:

            pass

        

        if success:

            werbung = WerbungDB.get_by_id(werbung_id)

            await message.reply_text(

                f"✅ **Text aktualisiert!**\n\n"

                f"Die Änderung ist sofort wirksam.",

                parse_mode='Markdown'

            )

        else:

            await message.reply_text("❌ Fehler beim Speichern")

    

    # ========== MEDIA ÄNDERN (NEU!) ==========

    

    async def handle_wverwalten_edit_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Startet Media-Bearbeitung"""

        query = update.callback_query

        await query.answer()

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        # State in context.user_data speichern

        context.user_data['editing_werbung_id'] = werbung_id

        context.user_data['waiting_for_media'] = True

        

        try:

            await query.message.delete()

        except:

            pass

        

        current_media = "🖼️ Bild" if werbung.get('media_type') == 'photo' else "🎥 Video" if werbung.get('media_type') == 'video' else "Kein Media"

        

        keyboard = [

            [InlineKeyboardButton("🗑️ Media entfernen", callback_data=f"wverwalten_media_remove:{werbung_id}")],

            [InlineKeyboardButton("◀️ Zurück", callback_data=f"wverwalten_edit:{werbung_id}")]

        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        await query.message.reply_text(

            f"📸 **Media ändern**\n\n"

            f"**Aktuell:** {current_media}\n\n"

            f"Sende mir ein **neues Bild oder Video**:\n\n"

            f"• 🖼️ Foto (JPG, PNG)\n"

            f"• 🎥 Video (MP4)\n\n"

            f"Oder nutze die Buttons unten:",

            reply_markup=reply_markup,

            parse_mode='Markdown'

        )

    

    async def handle_wverwalten_edit_media_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Verarbeitet neues Media (Foto/Video)"""

        user = update.effective_user

        message = update.message

        

        # Prüfe ob wir auf Media warten

        if not context.user_data.get('waiting_for_media'):

            return

        

        werbung_id = context.user_data.get('editing_werbung_id')

        

        if not werbung_id:

            await message.reply_text("❌ Session abgelaufen. Bitte versuche es erneut.")

            context.user_data.clear()

            return

        

        # Media extrahieren

        new_media_ids = []

        new_media_type = None

        

        if message.photo:

            file_id = message.photo[-1].file_id

            new_media_ids = [file_id]

            new_media_type = 'photo'

        elif message.video:

            file_id = message.video.file_id

            new_media_ids = [file_id]

            new_media_type = 'video'

        else:

            await message.reply_text("❌ Bitte sende ein Foto oder Video!")

            return

        

        # Update in DB

        success = WerbungDB.update(werbung_id, media_ids=new_media_ids, media_type=new_media_type)

        

        # Cleanup State

        context.user_data.pop('waiting_for_media', None)

        context.user_data.pop('editing_werbung_id', None)

        

        try:

            await message.delete()

        except:

            pass

        

        if success:

            media_emoji = "🖼️" if new_media_type == 'photo' else "🎥"

            await message.reply_text(

                f"✅ **Media aktualisiert!**\n\n"

                f"{media_emoji} Neues Media wurde gespeichert.",

                parse_mode='Markdown'

            )

        else:

            await message.reply_text("❌ Fehler beim Speichern")

    

    async def handle_wverwalten_media_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Entfernt Media von Werbung"""

        query = update.callback_query

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        # Media entfernen

        success = WerbungDB.update(werbung_id, media_ids=[], media_type=None)

        

        # Cleanup State falls gesetzt

        context.user_data.pop('waiting_for_media', None)

        context.user_data.pop('editing_werbung_id', None)

        

        if success:

            await query.answer("✅ Media entfernt", show_alert=False)

            

            try:

                await query.message.delete()

            except:

                pass

            

            werbung = WerbungDB.get_by_id(werbung_id)

            await query.message.reply_text("✅ Media erfolgreich entfernt!", parse_mode='Markdown')

        else:

            await query.answer("❌ Fehler beim Entfernen", show_alert=True)

    

    # ========== INTERVALL ÄNDERN ==========

    

    async def handle_wverwalten_change_interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Zeigt Intervall-Auswahl"""

        query = update.callback_query

        await query.answer()

        

        try:

            werbung_id = int(query.data.split(':')[1])

        except (IndexError, ValueError):

            await query.answer("Ungültige Werbung-ID", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await query.answer("Keine Berechtigung", show_alert=True)

            return

        

        current_intervall = werbung.get('intervall', IntervallTyp.EINMALIG)

        minutes = werbung.get('intervall_hours', 360)

        

        keyboard = [

            [

                InlineKeyboardButton(

                    "Einmalig" + (" ✅" if current_intervall == IntervallTyp.EINMALIG else ""),

                    callback_data=f"wverwalten_setint:{werbung_id}:einmalig"

                ),

                InlineKeyboardButton(

                    f"Minuten" + (" ✅" if current_intervall == IntervallTyp.STUENDLICH else ""),

                    callback_data=f"wverwalten_setint:{werbung_id}:stuendlich"

                )

            ],

            [

                InlineKeyboardButton(

                    "Täglich" + (" ✅" if current_intervall == IntervallTyp.TAEGLICH else ""),

                    callback_data=f"wverwalten_setint:{werbung_id}:taeglich"

                ),

                InlineKeyboardButton(

                    "Wöchentlich" + (" ✅" if current_intervall == IntervallTyp.WOECHENTLICH else ""),

                    callback_data=f"wverwalten_setint:{werbung_id}:woechentlich"

                )

            ],

            [InlineKeyboardButton("◀️ Zurück", callback_data=f"wverwalten_edit:{werbung_id}")]

        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        

        try:

            await query.message.edit_text(

                f"⏱️ **Intervall ändern**\n\n"

                f"Für: **{werbung['title']}**\n\n"

                f"Aktuell: **{current_intervall}** ({minutes} Min)\n\n"

                f"Wähle neues Intervall:",

                reply_markup=reply_markup,

                parse_mode='Markdown'

            )

        except BadRequest as e:

            logger.warning(f"Edit failed: {e}")

    

    async def handle_wverwalten_setinterval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Setzt neues Intervall"""

        query = update.callback_query

        

        try:

            parts = query.data.split(':')

            werbung_id = int(parts[1])

            new_intervall = parts[2]

        except (IndexError, ValueError):

            await self._safe_answer_callback(query, "Ungültige Daten", show_alert=True)

            return

        

        werbung = WerbungDB.get_by_id(werbung_id)

        

        if not werbung or werbung['user_id'] != update.effective_user.id:

            await self._safe_answer_callback(query, "Keine Berechtigung", show_alert=True)

            return

        

        # Für Minuten-Intervall: Spezialbehandlung

        if new_intervall == IntervallTyp.STUENDLICH:

            # State setzen für Minuten-Eingabe

            context.user_data['editing_werbung_id'] = werbung_id

            context.user_data['waiting_for_minutes'] = True

            

            try:

                await query.message.delete()

            except:

                pass

            

            await query.message.reply_text(

                f"⏰ **Minuten-Intervall**\n\n"

                f"Alle wie viele Minuten soll gepostet werden?\n\n"

                f"Aktuell: **{werbung.get('intervall_hours', 360)} Minuten**\n\n"

                f"Sende eine Zahl zwischen **1-1440 Minuten**:",

                parse_mode='Markdown'

            )

            await self._safe_answer_callback(query)

            return

        

        # Für andere Intervalle: Direkt setzen

        updates = {'intervall': new_intervall}

        

        if new_intervall == IntervallTyp.TAEGLICH:

            updates['intervall_time'] = '12:00'

        elif new_intervall == IntervallTyp.WOECHENTLICH:

            updates['intervall_days'] = [1, 3, 5]

            updates['intervall_time'] = '12:00'

        

        success = WerbungDB.update(werbung_id, **updates)

        

        if success:

            scheduler = get_scheduler()

            if scheduler:

                scheduler.remove_werbung_job(werbung_id)

                if new_intervall != IntervallTyp.EINMALIG:

                    scheduler.schedule_werbung(werbung_id)

            

            await self._safe_answer_callback(query, f"✅ Intervall: {new_intervall}")

            

            werbung = WerbungDB.get_by_id(werbung_id)

            await self._show_wverwalten_edit_view(query, werbung)

        else:

            await self._safe_answer_callback(query, "❌ Fehler beim Speichern", show_alert=True)

    

    async def handle_wverwalten_edit_minutes_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Verarbeitet Minuten-Eingabe beim Bearbeiten"""

        user = update.effective_user

        message = update.message

        

        # Prüfe ob wir auf Minuten warten

        if not context.user_data.get('waiting_for_minutes'):

            return

        

        werbung_id = context.user_data.get('editing_werbung_id')

        

        if not werbung_id:

            await message.reply_text("❌ Session abgelaufen. Bitte versuche es erneut.")

            context.user_data.clear()

            return

        

        try:

            minutes = int(message.text.strip())

            

            if minutes < 1 or minutes > 1440:

                await message.reply_text(

                    f"❌ **Ungültiger Wert!**\n\n"

                    f"Bitte gib eine Zahl zwischen **1 und 1440 Minuten** ein.\n\n"

                    f"Du hast eingegeben: {minutes}\n"

                    f"Versuche es erneut:",

                    parse_mode='Markdown'

                )

                return

            

            # Update in DB

            success = WerbungDB.update(werbung_id, intervall_hours=minutes, intervall=IntervallTyp.STUENDLICH)

            

            # Cleanup State

            context.user_data.pop('waiting_for_minutes', None)

            context.user_data.pop('editing_werbung_id', None)

            

            try:

                await message.delete()

            except:

                pass

            

            if success:

                # Scheduler aktualisieren

                scheduler = get_scheduler()

                if scheduler:

                    try:

                        scheduler.remove_werbung_job(werbung_id)

                        scheduler.schedule_werbung(werbung_id)

                        logger.info(f"✅ Scheduler aktualisiert für Werbung {werbung_id}: {minutes} Min")

                    except Exception as e:

                        logger.error(f"❌ Scheduler-Fehler: {e}")

                

                await message.reply_text(

                    f"✅ **Intervall aktualisiert!**\n\n"

                    f"Neues Intervall: Alle **{minutes} Minuten**",

                    parse_mode='Markdown'

                )

            else:

                await message.reply_text("❌ Fehler beim Speichern")

                

        except ValueError:

            await message.reply_text(

                f"❌ **Ungültige Eingabe!**\n\n"

                f"Bitte gib eine **ganze Zahl** zwischen 1 und 1440 ein.\n\n"

                f"Versuche es erneut:",

                parse_mode='Markdown'

            )

    

    # ========== UNIVERSAL MESSAGE HANDLER FÜR EDIT-FUNKTIONEN ==========

    

    async def handle_wverwalten_edit_message_router(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        """Universal Message Handler für alle Edit-Funktionen"""

        # Prüfe zuerst Minuten-Eingabe

        if context.user_data.get('waiting_for_minutes'):

            await self.handle_wverwalten_edit_minutes_message(update, context)

            return

        

        # Dann Text-Eingabe

        if context.user_data.get('waiting_for_text'):

            await self.handle_wverwalten_edit_text_message(update, context)

            return

        

        # Dann Media-Eingabe

        if context.user_data.get('waiting_for_media'):

            await self.handle_wverwalten_edit_media_message(update, context)

            return

        

        # Sonst ignorieren (für ConversationHandler)

def register_handlers(application):

    """Registriert alle Werbung-Handler"""

    handler = WerbungHandler()

    

    # Basic Commands

    application.add_handler(CommandHandler('start', handler.cmd_start))

    application.add_handler(CommandHandler('help', handler.cmd_help))

    application.add_handler(CommandHandler('groups', handler.cmd_groups))

    

    # Expand/Minimize Callbacks (group=-1 für höchste Priorität)

    application.add_handler(

        CallbackQueryHandler(handler.handle_expand, pattern=f'^{CallbackPrefix.WERBE_EXPAND}:'),

        group=-1

    )

    application.add_handler(

        CallbackQueryHandler(handler.handle_minimize, pattern=f'^{CallbackPrefix.WERBE_MINIMIZE}:'),

        group=-1

    )

    

    # ========== WVERWALTEN HANDLER (group=0 - vor ConversationHandler) ==========

    

    # Edit-View

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_edit, pattern='^wverwalten_edit:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_pause, pattern='^wverwalten_pause:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_activate, pattern='^wverwalten_activate:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_toggle_delete, pattern='^wverwalten_toggle_delete:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_delete_confirm, pattern='^wverwalten_delete_confirm:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_delete, pattern='^wverwalten_delete:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_back, pattern='^wverwalten_back$'), group=0)

    

    # Gruppen ändern (NEU: mit Mehrfachauswahl)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_change_groups, pattern='^wverwalten_groups:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_toggle_group, pattern='^wverwalten_toggle_group:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_groups_confirm, pattern='^wverwalten_groups_confirm$'), group=0)

    

    # Text ändern

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_edit_text, pattern='^wverwalten_text:'), group=0)

    

    # Media ändern (NEU!)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_edit_media, pattern='^wverwalten_media:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_media_remove, pattern='^wverwalten_media_remove:'), group=0)

    

    # Intervall ändern

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_change_interval, pattern='^wverwalten_interval:'), group=0)

    application.add_handler(CallbackQueryHandler(handler.handle_wverwalten_setinterval, pattern='^wverwalten_setint:'), group=0)

    

    # Universal MessageHandler für alle Edit-Funktionen (group=0)

    application.add_handler(

        MessageHandler(

            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,

            handler.handle_wverwalten_edit_message_router

        ),

        group=0

    )

    

    # Media-Handler für Edit-Funktionen (group=0)

    application.add_handler(

        MessageHandler(

            (filters.PHOTO | filters.VIDEO) & filters.ChatType.PRIVATE,

            handler.handle_wverwalten_edit_message_router

        ),

        group=0

    )

    

    # ========== HAUPTWERBUNGS-CONVERSATIONHANDLER (group=1) ==========

    

    conv_handler = ConversationHandler(

        entry_points=[

            CommandHandler('werbe', handler.cmd_werbe),

            MessageHandler(

                filters.Regex(r'^📢 Werbung') & filters.ChatType.PRIVATE,

                handler.cmd_werbe

            )

        ],

        states={

            handler.WAITING_INPUT: [

                MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handler.handle_input),

                CallbackQueryHandler(handler.create_werbung, pattern='^werbe_create$'),

                CallbackQueryHandler(handler.skip_ai, pattern='^werbe_skip_ai$'),

                CallbackQueryHandler(handler.add_manual_button, pattern='^werbe_add_manual_button$')

            ],

            handler.PREVIEW: [

                CallbackQueryHandler(handler.post_settings, pattern='^werbe_post$'),

                CallbackQueryHandler(handler.regenerate, pattern='^werbe_regenerate$'),

                CallbackQueryHandler(handler.cancel, pattern='^werbe_cancel$')

            ],

            handler.SETTINGS: [

                CallbackQueryHandler(handler.select_group, pattern='^werbe_select_group:'),

                CallbackQueryHandler(handler.groups_done, pattern='^werbe_groups_done$'),

                CallbackQueryHandler(handler.set_interval, pattern='^werbe_interval:'),

                CallbackQueryHandler(handler.set_timer, pattern='^werbe_set_timer$'),

                CallbackQueryHandler(handler.set_timer_value, pattern='^werbe_timer:'),

                CallbackQueryHandler(handler.timer_back, pattern='^werbe_timer_back$'),

                CallbackQueryHandler(handler.toggle_pin, pattern='^werbe_toggle_pin'),

                CallbackQueryHandler(handler.toggle_delete_old, pattern='^werbe_toggle_delete'),

                CallbackQueryHandler(handler.set_start_date, pattern='^werbe_set_start_date$'),

                CallbackQueryHandler(handler.set_end_date, pattern='^werbe_set_end_date$'),

                CallbackQueryHandler(handler.confirm_post, pattern='^werbe_confirm_post$')

            ],

            handler.MINUTES_INPUT: [

                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_minutes_input)

            ],

            handler.START_DATE_INPUT: [

                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_start_date_input)

            ],

            handler.END_DATE_INPUT: [

                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_end_date_input)

            ],

            handler.MANUAL_BUTTON_TEXT: [

                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_manual_button_text)

            ],

            handler.MANUAL_BUTTON_URL: [

                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_manual_button_url)

            ]

        },

        fallbacks=[

            CallbackQueryHandler(handler.cancel, pattern='^werbe_cancel$')

        ],

        per_message=False,

        per_chat=True,

        per_user=True

    )

    

    application.add_handler(conv_handler, group=1)

    

    logger.info("✅ Werbung-Handler registriert (Minuten-System 1-1440 + Edit-Funktionen + Media-Upload + Gruppen-Mehrfachauswahl)")