"""
setup_shop.py - Initial Shop Setup Script
Dieses Script erstellt die Datenbank-Tabellen und fügt Beispiel-Daten hinzu

AUSFÜHREN:
python setup_shop.py
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession

# Import all models to register them
from models.user import User
from models.cart import Cart, Order, OrderItem
from models.shop import ShopCategory, ShopSubcategory, ShopProduct, ShopSettings, DEFAULT_SHOP_SETTINGS
from db import engine, Base, AsyncSessionLocal
from services.shop import ShopService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables():
    """Create all database tables"""
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Tables created!")


async def initialize_settings(session: AsyncSession):
    """Initialize default shop settings"""
    logger.info("Initializing shop settings...")
    
    for key, value in DEFAULT_SHOP_SETTINGS.items():
        existing = await ShopService.get_setting(key, session)
        if existing is None:
            await ShopService.set_setting(key, value, f"Default {key}", session)
            logger.info(f"  ✅ Setting: {key} = {value}")
        else:
            logger.info(f"  ⏭️  Setting already exists: {key}")
    
    logger.info("✅ Settings initialized!")


async def create_example_data(session: AsyncSession):
    """Create example shop structure (optional)"""
    logger.info("Creating example data...")
    
    # Check if data already exists
    categories = await ShopService.get_all_categories(session, active_only=False)
    if categories:
        logger.info("  ⏭️  Example data already exists, skipping...")
        return
    
    # Kategorie 1: Schuhe
    cat_schuhe = await ShopService.create_category(
        name="Schuhe",
        emoji="👟",
        description="Alle Arten von Schuhen",
        session=session
    )
    logger.info(f"  ✅ Category: {cat_schuhe.emoji} {cat_schuhe.name}")
    
    # Subkategorie: Sneaker
    subcat_sneaker = await ShopService.create_subcategory(
        category_id=cat_schuhe.id,
        name="Sneaker",
        emoji="👟",
        description="Sportschuhe und Sneaker",
        session=session
    )
    logger.info(f"    ✅ Subcategory: {subcat_sneaker.emoji} {subcat_sneaker.name}")
    
    # Produkt: Nike Air Max
    prod_nike = await ShopService.create_product(
        subcategory_id=subcat_sneaker.id,
        name="Nike Air Max",
        emoji="👟",
        description="Classic Nike Air Max Sneaker in verschiedenen Größen",
        price_per_unit=129.99,
        unit="Paar",
        min_quantity=1,
        max_quantity=10,
        session=session
    )
    logger.info(f"      ✅ Product: {prod_nike.emoji} {prod_nike.name} ({prod_nike.price_per_unit}€)")
    
    # Produkt: Adidas Yeezy
    prod_adidas = await ShopService.create_product(
        subcategory_id=subcat_sneaker.id,
        name="Adidas Yeezy Boost 350",
        emoji="👟",
        description="Limitierte Yeezy Boost 350 V2",
        price_per_unit=249.99,
        unit="Paar",
        min_quantity=1,
        max_quantity=5,
        session=session
    )
    logger.info(f"      ✅ Product: {prod_adidas.emoji} {prod_adidas.name} ({prod_adidas.price_per_unit}€)")
    
    # Subkategorie: Stiefel
    subcat_stiefel = await ShopService.create_subcategory(
        category_id=cat_schuhe.id,
        name="Stiefel",
        emoji="🥾",
        description="Winterstiefel und Boots",
        session=session
    )
    logger.info(f"    ✅ Subcategory: {subcat_stiefel.emoji} {subcat_stiefel.name}")
    
    # Produkt: Timberland Boots
    prod_timberland = await ShopService.create_product(
        subcategory_id=subcat_stiefel.id,
        name="Timberland 6-Inch Premium Boot",
        emoji="🥾",
        description="Classic Timberland Boots wasserdicht",
        price_per_unit=189.99,
        unit="Paar",
        min_quantity=1,
        max_quantity=10,
        session=session
    )
    logger.info(f"      ✅ Product: {prod_timberland.emoji} {prod_timberland.name} ({prod_timberland.price_per_unit}€)")
    
    # Kategorie 2: Kleidung
    cat_kleidung = await ShopService.create_category(
        name="Kleidung",
        emoji="👕",
        description="Mode und Bekleidung",
        session=session
    )
    logger.info(f"  ✅ Category: {cat_kleidung.emoji} {cat_kleidung.name}")
    
    # Subkategorie: T-Shirts
    subcat_tshirts = await ShopService.create_subcategory(
        category_id=cat_kleidung.id,
        name="T-Shirts",
        emoji="👕",
        description="T-Shirts und Oberteile",
        session=session
    )
    logger.info(f"    ✅ Subcategory: {subcat_tshirts.emoji} {subcat_tshirts.name}")
    
    # Produkt: Basic T-Shirt
    prod_basic_tshirt = await ShopService.create_product(
        subcategory_id=subcat_tshirts.id,
        name="Basic T-Shirt",
        emoji="👕",
        description="Einfaches Basic T-Shirt 100% Baumwolle",
        price_per_unit=19.99,
        unit="Stück",
        min_quantity=1,
        max_quantity=50,
        session=session
    )
    logger.info(f"      ✅ Product: {prod_basic_tshirt.emoji} {prod_basic_tshirt.name} ({prod_basic_tshirt.price_per_unit}€)")
    
    logger.info("✅ Example data created!")


async def main():
    """Main setup function"""
    logger.info("="*50)
    logger.info("🏪 Shop Setup Script")
    logger.info("="*50)
    
    # Step 1: Create tables
    await create_tables()
    
    # Step 2: Initialize settings
    async with AsyncSessionLocal() as session:
        await initialize_settings(session)
    
    # Step 3: Create example data
    print("\n❓ Möchtest du Beispiel-Daten erstellen? (y/n): ", end="")
    choice = input().strip().lower()
    
    if choice == 'y':
        async with AsyncSessionLocal() as session:
            await create_example_data(session)
    else:
        logger.info("⏭️  Skipping example data creation")
    
    logger.info("="*50)
    logger.info("✅ Setup complete!")
    logger.info("="*50)
    logger.info("📝 Next steps:")
    logger.info("  1. Start your bot")
    logger.info("  2. Use /start and go to 🔑 Admin Menu")
    logger.info("  3. Click 🏪 Shop-Verwaltung")
    logger.info("  4. Add your own categories, subcategories, and products!")
    logger.info("="*50)


if __name__ == "__main__":
    asyncio.run(main())
