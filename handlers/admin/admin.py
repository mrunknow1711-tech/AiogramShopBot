"""
handlers/admin/shop_management.py - Admin Shop-Verwaltung VOLLSTÄNDIG
Erstelle dieses File: handlers/admin/shop_management.py
"""
from aiogram import types, F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import logging

from callbacks import AdminShopCallback, ShopManagementAction
from states.admin_shop_states import AdminShopStates
from services.shop import ShopService
from utils.custom_filters import IsAdminFilter
import config

logger = logging.getLogger(__name__)
admin_shop_router = Router()


def format_price(amount: float) -> str:
    """Format price"""
    return f"{amount:.2f}€"


# ===== MAIN MENU =====

@admin_shop_router.callback_query(
    F.data == "admin_shop_management",
    IsAdminFilter()
)
async def show_shop_management_menu(callback: CallbackQuery, state: FSMContext):
    """Haupt Shop-Verwaltungsmenü"""
    await state.clear()
    
    text = (
        "🏪 <b>Shop-Verwaltung</b>\n\n"
        "Hier kannst du den kompletten Shop verwalten:\n"
        "• Kategorien\n"
        "• Subkategorien\n"
        "• Produkte\n"
        "• Einstellungen"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📁 Kategorien verwalten",
        callback_data=AdminShopCallback.create(
            level=1,
            action=ShopManagementAction.VIEW_CATEGORIES
        )
    )
    builder.button(
        text="⚙️ Einstellungen",
        callback_data=AdminShopCallback.create(
            level=1,
            action=ShopManagementAction.SETTINGS
        )
    )
    builder.button(
        text="🔙 Zurück",
        callback_data="admin_menu"
    )
    builder.adjust(1)
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


# ===== CATEGORIES =====

@admin_shop_router.callback_query(
    AdminShopCallback.filter(F.action == ShopManagementAction.VIEW_CATEGORIES),
    IsAdminFilter()
)
async def view_categories(callback: CallbackQuery, callback_data: AdminShopCallback, 
                         state: FSMContext, session: AsyncSession | Session):
    """Liste aller Kategorien"""
    await state.clear()
    
    categories = await ShopService.get_all_categories(session, active_only=False)
    
    text = "📁 <b>Kategorien</b>\n\n"
    if categories:
        for cat in categories:
            status = "✅" if cat.is_active else "❌"
            text += f"{status} {cat.emoji} {cat.name} (ID: {cat.id})\n"
    else:
        text += "Keine Kategorien vorhanden."
    
    builder = InlineKeyboardBuilder()
    
    # Kategorie-Buttons
    for cat in categories:
        builder.button(
            text=f"{cat.emoji} {cat.name}",
            callback_data=AdminShopCallback.create(
                level=2,
                action=ShopManagementAction.VIEW_SUBCATEGORIES,
                category_id=cat.id
            )
        )
    
    # Actions
    builder.button(
        text="➕ Neue Kategorie",
        callback_data=AdminShopCallback.create(
            level=2,
            action=ShopManagementAction.ADD_CATEGORY
        )
    )
    builder.button(
        text="🔙 Zurück",
        callback_data="admin_shop_management"
    )
    
    builder.adjust(2, 1, 1)
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


@admin_shop_router.callback_query(
    AdminShopCallback.filter(F.action == ShopManagementAction.ADD_CATEGORY),
    IsAdminFilter()
)
async def start_add_category(callback: CallbackQuery, state: FSMContext):
    """Start: Kategorie hinzufügen"""
    await state.set_state(AdminShopStates.waiting_for_category_name)
    
    text = (
        "➕ <b>Neue Kategorie erstellen</b>\n\n"
        "Schritt 1/3: Name der Kategorie\n\n"
        "Bitte sende den Namen der Kategorie (z.B. 'Schuhe', 'Kleidung'):"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Abbrechen", callback_data="admin_shop_management")
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


@admin_shop_router.message(AdminShopStates.waiting_for_category_name, IsAdminFilter())
async def process_category_name(message: Message, state: FSMContext):
    """Process category name"""
    name = message.text.strip()
    
    if len(name) < 2 or len(name) > 100:
        await message.answer("❌ Name muss 2-100 Zeichen lang sein!")
        return
    
    await state.update_data(category_name=name)
    await state.set_state(AdminShopStates.waiting_for_category_emoji)
    
    text = (
        f"✅ Name gesetzt: <b>{name}</b>\n\n"
        f"Schritt 2/3: Emoji\n\n"
        f"Bitte sende ein Emoji für die Kategorie (z.B. 👟, 👕, 🎒):"
    )
    
    try:
        await message.delete()
    except:
        pass
    
    await message.answer(text)


@admin_shop_router.message(AdminShopStates.waiting_for_category_emoji, IsAdminFilter())
async def process_category_emoji(message: Message, state: FSMContext):
    """Process category emoji"""
    emoji = message.text.strip()
    
    if len(emoji) > 10:
        await message.answer("❌ Bitte nur ein Emoji senden!")
        return
    
    await state.update_data(category_emoji=emoji)
    await state.set_state(AdminShopStates.waiting_for_category_description)
    
    text = (
        f"✅ Emoji gesetzt: {emoji}\n\n"
        f"Schritt 3/3: Beschreibung (optional)\n\n"
        f"Sende eine Beschreibung oder 'skip' zum Überspringen:"
    )
    
    try:
        await message.delete()
    except:
        pass
    
    await message.answer(text)


@admin_shop_router.message(AdminShopStates.waiting_for_category_description, IsAdminFilter())
async def process_category_description(message: Message, state: FSMContext, session: AsyncSession | Session):
    """Process category description and create"""
    description = message.text.strip() if message.text.lower() != "skip" else ""
    
    data = await state.get_data()
    name = data.get("category_name")
    emoji = data.get("category_emoji")
    
    # Create category
    category = await ShopService.create_category(name, emoji, description, session)
    
    await state.clear()
    
    try:
        await message.delete()
    except:
        pass
    
    if category:
        text = (
            f"✅ <b>Kategorie erstellt!</b>\n\n"
            f"{emoji} <b>{name}</b>\n"
            f"ID: {category.id}\n"
            f"Beschreibung: {description or 'Keine'}"
        )
    else:
        text = "❌ Fehler beim Erstellen der Kategorie!"
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📁 Zu Kategorien",
        callback_data=AdminShopCallback.create(
            level=1,
            action=ShopManagementAction.VIEW_CATEGORIES
        )
    )
    
    await message.answer(text, reply_markup=builder.as_markup())


# ===== SUBCATEGORIES =====

@admin_shop_router.callback_query(
    AdminShopCallback.filter(F.action == ShopManagementAction.VIEW_SUBCATEGORIES),
    IsAdminFilter()
)
async def view_subcategories(callback: CallbackQuery, callback_data: AdminShopCallback,
                            state: FSMContext, session: AsyncSession | Session):
    """Liste aller Subkategorien einer Kategorie"""
    await state.clear()
    
    category_id = callback_data.category_id
    category = await ShopService.get_category_by_id(category_id, session)
    
    if not category:
        await callback.answer("❌ Kategorie nicht gefunden!", show_alert=True)
        return
    
    subcategories = await ShopService.get_subcategories_by_category(category_id, session, active_only=False)
    
    text = f"📂 <b>Subkategorien von {category.emoji} {category.name}</b>\n\n"
    if subcategories:
        for subcat in subcategories:
            status = "✅" if subcat.is_active else "❌"
            text += f"{status} {subcat.emoji} {subcat.name} (ID: {subcat.id})\n"
    else:
        text += "Keine Subkategorien vorhanden."
    
    builder = InlineKeyboardBuilder()
    
    # Subkategorie-Buttons
    for subcat in subcategories:
        builder.button(
            text=f"{subcat.emoji} {subcat.name}",
            callback_data=AdminShopCallback.create(
                level=3,
                action=ShopManagementAction.VIEW_PRODUCTS,
                category_id=category_id,
                subcategory_id=subcat.id
            )
        )
    
    # Actions
    builder.button(
        text="➕ Neue Subkategorie",
        callback_data=AdminShopCallback.create(
            level=3,
            action=ShopManagementAction.ADD_SUBCATEGORY,
            category_id=category_id
        )
    )
    builder.button(
        text="🗑️ Kategorie löschen",
        callback_data=AdminShopCallback.create(
            level=2,
            action=ShopManagementAction.DELETE_CATEGORY,
            category_id=category_id
        )
    )
    builder.button(
        text="🔙 Zurück",
        callback_data=AdminShopCallback.create(
            level=1,
            action=ShopManagementAction.VIEW_CATEGORIES
        )
    )
    
    builder.adjust(2, 1, 1, 1)
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


@admin_shop_router.callback_query(
    AdminShopCallback.filter(F.action == ShopManagementAction.ADD_SUBCATEGORY),
    IsAdminFilter()
)
async def start_add_subcategory(callback: CallbackQuery, callback_data: AdminShopCallback, state: FSMContext):
    """Start: Subkategorie hinzufügen"""
    category_id = callback_data.category_id
    await state.update_data(parent_category_id=category_id)
    await state.set_state(AdminShopStates.waiting_for_subcategory_name)
    
    text = (
        "➕ <b>Neue Subkategorie erstellen</b>\n\n"
        "Schritt 1/3: Name der Subkategorie\n\n"
        "Bitte sende den Namen (z.B. 'Sneaker', 'Stiefel', 'Sandalen'):"
    )
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.message.answer(text)
    await callback.answer()


@admin_shop_router.message(AdminShopStates.waiting_for_subcategory_name, IsAdminFilter())
async def process_subcategory_name(message: Message, state: FSMContext):
    """Process subcategory name"""
    name = message.text.strip()
    
    if len(name) < 2 or len(name) > 100:
        await message.answer("❌ Name muss 2-100 Zeichen lang sein!")
        return
    
    await state.update_data(subcategory_name=name)
    await state.set_state(AdminShopStates.waiting_for_subcategory_emoji)
    
    text = (
        f"✅ Name gesetzt: <b>{name}</b>\n\n"
        f"Schritt 2/3: Emoji\n\n"
        f"Bitte sende ein Emoji:"
    )
    
    try:
        await message.delete()
    except:
        pass
    
    await message.answer(text)


@admin_shop_router.message(AdminShopStates.waiting_for_subcategory_emoji, IsAdminFilter())
async def process_subcategory_emoji(message: Message, state: FSMContext):
    """Process subcategory emoji"""
    emoji = message.text.strip()
    
    if len(emoji) > 10:
        await message.answer("❌ Bitte nur ein Emoji senden!")
        return
    
    await state.update_data(subcategory_emoji=emoji)
    await state.set_state(AdminShopStates.waiting_for_subcategory_description)
    
    text = (
        f"✅ Emoji gesetzt: {emoji}\n\n"
        f"Schritt 3/3: Beschreibung (optional)\n\n"
        f"Sende eine Beschreibung oder 'skip' zum Überspringen:"
    )
    
    try:
        await message.delete()
    except:
        pass
    
    await message.answer(text)


@admin_shop_router.message(AdminShopStates.waiting_for_subcategory_description, IsAdminFilter())
async def process_subcategory_description(message: Message, state: FSMContext, session: AsyncSession | Session):
    """Process subcategory description and create"""
    description = message.text.strip() if message.text.lower() != "skip" else ""
    
    data = await state.get_data()
    category_id = data.get("parent_category_id")
    name = data.get("subcategory_name")
    emoji = data.get("subcategory_emoji")
    
    # Create subcategory
    subcategory = await ShopService.create_subcategory(category_id, name, emoji, description, session)
    
    await state.clear()
    
    try:
        await message.delete()
    except:
        pass
    
    if subcategory:
        text = (
            f"✅ <b>Subkategorie erstellt!</b>\n\n"
            f"{emoji} <b>{name}</b>\n"
            f"ID: {subcategory.id}\n"
            f"Beschreibung: {description or 'Keine'}"
        )
    else:
        text = "❌ Fehler beim Erstellen der Subkategorie!"
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📂 Zu Subkategorien",
        callback_data=AdminShopCallback.create(
            level=2,
            action=ShopManagementAction.VIEW_SUBCATEGORIES,
            category_id=category_id
        )
    )
    
    await message.answer(text, reply_markup=builder.as_markup())


# ===== PRODUCTS ===== (Teil 1 - Wird fortgesetzt)

@admin_shop_router.callback_query(
    AdminShopCallback.filter(F.action == ShopManagementAction.VIEW_PRODUCTS),
    IsAdminFilter()
)
async def view_products(callback: CallbackQuery, callback_data: AdminShopCallback,
                       state: FSMContext, session: AsyncSession | Session):
    """Liste aller Produkte einer Subkategorie"""
    await state.clear()
    
    subcategory_id = callback_data.subcategory_id
    category_id = callback_data.category_id
    
    subcategory = await ShopService.get_subcategory_by_id(subcategory_id, session)
    if not subcategory:
        await callback.answer("❌ Subkategorie nicht gefunden!", show_alert=True)
        return
    
    products = await ShopService.get_products_by_subcategory(subcategory_id, session, active_only=False)
    
    text = f"📦 <b>Produkte in {subcategory.emoji} {subcategory.name}</b>\n\n"
    if products:
        for prod in products:
            status = "✅" if prod.is_active else "❌"
            stock = "📦" if prod.in_stock else "❌"
            price = format_price(prod.price_per_unit)
            text += (
                f"{status}{stock} {prod.emoji} <b>{prod.name}</b>\n"
                f"   Preis: {price}/{prod.unit} | Min: {prod.min_quantity}{prod.unit}\n"
            )
    else:
        text += "Keine Produkte vorhanden."
    
    builder = InlineKeyboardBuilder()
    
    # Produkt-Buttons (max 10)
    for prod in products[:10]:
        builder.button(
            text=f"{prod.emoji} {prod.name}",
            callback_data=AdminShopCallback.create(
                level=4,
                action=ShopManagementAction.EDIT_PRODUCT,
                subcategory_id=subcategory_id,
                product_id=prod.id
            )
        )
    
    # Actions
    builder.button(
        text="➕ Neues Produkt",
        callback_data=AdminShopCallback.create(
            level=4,
            action=ShopManagementAction.ADD_PRODUCT,
            category_id=category_id,
            subcategory_id=subcategory_id
        )
    )
    builder.button(
        text="🗑️ Subkategorie löschen",
        callback_data=AdminShopCallback.create(
            level=3,
            action=ShopManagementAction.DELETE_SUBCATEGORY,
            category_id=category_id,
            subcategory_id=subcategory_id
        )
    )
    builder.button(
        text="🔙 Zurück",
        callback_data=AdminShopCallback.create(
            level=2,
            action=ShopManagementAction.VIEW_SUBCATEGORIES,
            category_id=category_id
        )
    )
    
    builder.adjust(2, 1, 1, 1)
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


# ===== PRODUCT ADD (Multi-Step) =====

@admin_shop_router.callback_query(
    AdminShopCallback.filter(F.action == ShopManagementAction.ADD_PRODUCT),
    IsAdminFilter()
)
async def start_add_product(callback: CallbackQuery, callback_data: AdminShopCallback, state: FSMContext):
    """Start: Produkt hinzufügen - Step 1/7"""
    await state.update_data(
        parent_subcategory_id=callback_data.subcategory_id,
        parent_category_id=callback_data.category_id
    )
    await state.set_state(AdminShopStates.waiting_for_product_name)
    
    text = (
        "➕ <b>Neues Produkt erstellen</b>\n\n"
        "Schritt 1/7: Produktname\n\n"
        "Bitte sende den Namen des Produkts:"
    )
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.message.answer(text)
    await callback.answer()


@admin_shop_router.message(AdminShopStates.waiting_for_product_name, IsAdminFilter())
async def process_product_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 200:
        await message.answer("❌ Name muss 2-200 Zeichen lang sein!")
        return
    
    await state.update_data(product_name=name)
    await state.set_state(AdminShopStates.waiting_for_product_emoji)
    
    await message.answer(
        f"✅ Name: <b>{name}</b>\n\n"
        f"Schritt 2/7: Emoji\n\n"
        f"Bitte sende ein Emoji:"
    )


@admin_shop_router.message(AdminShopStates.waiting_for_product_emoji, IsAdminFilter())
async def process_product_emoji(message: Message, state: FSMContext):
    emoji = message.text.strip()
    await state.update_data(product_emoji=emoji)
    await state.set_state(AdminShopStates.waiting_for_product_price)
    
    await message.answer(
        f"✅ Emoji: {emoji}\n\n"
        f"Schritt 3/7: Preis pro Einheit\n\n"
        f"Bitte sende den Preis (z.B. 89.99):"
    )


@admin_shop_router.message(AdminShopStates.waiting_for_product_price, IsAdminFilter())
async def process_product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except:
        await message.answer("❌ Bitte gib einen gültigen Preis ein (z.B. 89.99)!")
        return
    
    await state.update_data(product_price=price)
    await state.set_state(AdminShopStates.waiting_for_product_unit)
    
    await message.answer(
        f"✅ Preis: {format_price(price)}\n\n"
        f"Schritt 4/7: Einheit\n\n"
        f"Bitte sende die Einheit (z.B. 'Stück', 'g', 'kg', 'ml'):"
    )


@admin_shop_router.message(AdminShopStates.waiting_for_product_unit, IsAdminFilter())
async def process_product_unit(message: Message, state: FSMContext):
    unit = message.text.strip()
    await state.update_data(product_unit=unit)
    await state.set_state(AdminShopStates.waiting_for_product_min_quantity)
    
    await message.answer(
        f"✅ Einheit: {unit}\n\n"
        f"Schritt 5/7: Mindestmenge\n\n"
        f"Bitte sende die Mindestmenge (z.B. 1 oder 10):"
    )


@admin_shop_router.message(AdminShopStates.waiting_for_product_min_quantity, IsAdminFilter())
async def process_product_min_quantity(message: Message, state: FSMContext):
    try:
        min_qty = int(message.text.strip())
        if min_qty < 1:
            raise ValueError
    except:
        await message.answer("❌ Bitte gib eine gültige Zahl ein (min. 1)!")
        return
    
    await state.update_data(product_min_quantity=min_qty)
    await state.set_state(AdminShopStates.waiting_for_product_max_quantity)
    
    await message.answer(
        f"✅ Mindestmenge: {min_qty}\n\n"
        f"Schritt 6/7: Maximalmenge\n\n"
        f"Bitte sende die Maximalmenge (z.B. 2000):"
    )


@admin_shop_router.message(AdminShopStates.waiting_for_product_max_quantity, IsAdminFilter())
async def process_product_max_quantity(message: Message, state: FSMContext):
    try:
        max_qty = int(message.text.strip())
        if max_qty < 1:
            raise ValueError
    except:
        await message.answer("❌ Bitte gib eine gültige Zahl ein!")
        return
    
    await state.update_data(product_max_quantity=max_qty)
    await state.set_state(AdminShopStates.waiting_for_product_description)
    
    await message.answer(
        f"✅ Maximalmenge: {max_qty}\n\n"
        f"Schritt 7/7: Beschreibung (optional)\n\n"
        f"Sende eine Beschreibung oder 'skip' zum Überspringen:"
    )


@admin_shop_router.message(AdminShopStates.waiting_for_product_description, IsAdminFilter())
async def process_product_description(message: Message, state: FSMContext, session: AsyncSession | Session):
    description = message.text.strip() if message.text.lower() != "skip" else ""
    
    data = await state.get_data()
    subcategory_id = data.get("parent_subcategory_id")
    category_id = data.get("parent_category_id")
    
    # Create product
    product = await ShopService.create_product(
        subcategory_id=subcategory_id,
        name=data.get("product_name"),
        emoji=data.get("product_emoji"),
        description=description,
        price_per_unit=data.get("product_price"),
        unit=data.get("product_unit"),
        min_quantity=data.get("product_min_quantity"),
        max_quantity=data.get("product_max_quantity"),
        session=session
    )
    
    await state.clear()
    
    try:
        await message.delete()
    except:
        pass
    
    if product:
        text = (
            f"✅ <b>Produkt erstellt!</b>\n\n"
            f"{product.emoji} <b>{product.name}</b>\n"
            f"Preis: {format_price(product.price_per_unit)}/{product.unit}\n"
            f"Menge: {product.min_quantity}-{product.max_quantity}{product.unit}\n"
            f"ID: {product.id}"
        )
    else:
        text = "❌ Fehler beim Erstellen des Produkts!"
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📦 Zu Produkten",
        callback_data=AdminShopCallback.create(
            level=3,
            action=ShopManagementAction.VIEW_PRODUCTS,
            category_id=category_id,
            subcategory_id=subcategory_id
        )
    )
    
    await message.answer(text, reply_markup=builder.as_markup())


# ===== DELETE HANDLERS =====

@admin_shop_router.callback_query(
    AdminShopCallback.filter(F.action == ShopManagementAction.DELETE_CATEGORY),
    IsAdminFilter()
)
async def confirm_delete_category(callback: CallbackQuery, callback_data: AdminShopCallback,
                                 session: AsyncSession | Session):
    """Confirm category deletion"""
    if not callback_data.confirmation:
        category = await ShopService.get_category_by_id(callback_data.category_id, session)
        
        text = (
            f"⚠️ <b>Kategorie löschen?</b>\n\n"
            f"Kategorie: {category.emoji} {category.name}\n\n"
            f"❗️ WARNUNG: Alle Subkategorien und Produkte werden gelöscht!"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(
            text="✅ Ja, löschen",
            callback_data=AdminShopCallback.create(
                level=2,
                action=ShopManagementAction.DELETE_CATEGORY,
                category_id=callback_data.category_id,
                confirmation=True
            )
        )
        builder.button(
            text="❌ Abbrechen",
            callback_data=AdminShopCallback.create(
                level=2,
                action=ShopManagementAction.VIEW_SUBCATEGORIES,
                category_id=callback_data.category_id
            )
        )
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
    else:
        # Delete confirmed
        success = await ShopService.delete_category(callback_data.category_id, session)
        
        if success:
            await callback.answer("✅ Kategorie gelöscht!", show_alert=True)
        else:
            await callback.answer("❌ Fehler beim Löschen!", show_alert=True)
        
        # Redirect to categories list
        await view_categories(callback, callback_data, None, session)


@admin_shop_router.callback_query(
    AdminShopCallback.filter(F.action == ShopManagementAction.DELETE_SUBCATEGORY),
    IsAdminFilter()
)
async def confirm_delete_subcategory(callback: CallbackQuery, callback_data: AdminShopCallback,
                                    session: AsyncSession | Session):
    """Confirm subcategory deletion"""
    if not callback_data.confirmation:
        subcategory = await ShopService.get_subcategory_by_id(callback_data.subcategory_id, session)
        
        text = (
            f"⚠️ <b>Subkategorie löschen?</b>\n\n"
            f"Subkategorie: {subcategory.emoji} {subcategory.name}\n\n"
            f"❗️ WARNUNG: Alle Produkte werden gelöscht!"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(
            text="✅ Ja, löschen",
            callback_data=AdminShopCallback.create(
                level=3,
                action=ShopManagementAction.DELETE_SUBCATEGORY,
                category_id=callback_data.category_id,
                subcategory_id=callback_data.subcategory_id,
                confirmation=True
            )
        )
        builder.button(
            text="❌ Abbrechen",
            callback_data=AdminShopCallback.create(
                level=3,
                action=ShopManagementAction.VIEW_PRODUCTS,
                category_id=callback_data.category_id,
                subcategory_id=callback_data.subcategory_id
            )
        )
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
    else:
        # Delete confirmed
        success = await ShopService.delete_subcategory(callback_data.subcategory_id, session)
        
        if success:
            await callback.answer("✅ Subkategorie gelöscht!", show_alert=True)
        else:
            await callback.answer("❌ Fehler beim Löschen!", show_alert=True)
        
        # Redirect to subcategories list
        await view_subcategories(callback, callback_data, None, session)


# ===== SETTINGS =====

@admin_shop_router.callback_query(
    AdminShopCallback.filter(F.action == ShopManagementAction.SETTINGS),
    IsAdminFilter()
)
async def show_settings(callback: CallbackQuery, session: AsyncSession | Session):
    """Shop-Einstellungen anzeigen"""
    
    shipping_hausdrop = await ShopService.get_setting("shipping_hausdrop_cost", session, "15.00")
    shipping_packstation = await ShopService.get_setting("shipping_packstation_cost", session, "15.00")
    currency = await ShopService.get_setting("currency", session, "EUR")
    
    text = (
        f"⚙️ <b>Shop-Einstellungen</b>\n\n"
        f"🏠 Hausdrop: {shipping_hausdrop}€\n"
        f"📦 Packstation: {shipping_packstation}€\n"
        f"💰 Währung: {currency}\n\n"
        f"Funktion wird in Phase 3 erweitert..."
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔙 Zurück",
        callback_data="admin_shop_management"
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()
