"""
services/shop.py - Shop Management Service
Erstelle dieses File: services/shop.py
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, delete, update
from typing import List, Optional, Tuple
import logging

from models.shop import ShopCategory, ShopSubcategory, ShopProduct, ShopSettings, DEFAULT_SHOP_SETTINGS

logger = logging.getLogger(__name__)


class ShopService:
    """Service für Shop-Verwaltung"""
    
    # ===== CATEGORIES =====
    
    @staticmethod
    async def get_all_categories(session: AsyncSession | Session, active_only: bool = True) -> List[ShopCategory]:
        """Get all categories"""
        try:
            stmt = select(ShopCategory).order_by(ShopCategory.sort_order, ShopCategory.name)
            if active_only:
                stmt = stmt.where(ShopCategory.is_active == True)
            result = await session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
    
    @staticmethod
    async def get_category_by_id(category_id: int, session: AsyncSession | Session) -> Optional[ShopCategory]:
        """Get category by ID"""
        try:
            stmt = select(ShopCategory).where(ShopCategory.id == category_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting category: {e}")
            return None
    
    @staticmethod
    async def create_category(name: str, emoji: str, description: str, session: AsyncSession | Session) -> Optional[ShopCategory]:
        """Create new category"""
        try:
            category = ShopCategory(
                name=name,
                emoji=emoji,
                description=description,
                is_active=True
            )
            session.add(category)
            await session.commit()
            await session.refresh(category)
            return category
        except Exception as e:
            logger.error(f"Error creating category: {e}")
            await session.rollback()
            return None
    
    @staticmethod
    async def update_category(category_id: int, name: str = None, emoji: str = None, 
                             description: str = None, is_active: bool = None,
                             session: AsyncSession | Session = None) -> bool:
        """Update category"""
        try:
            updates = {}
            if name is not None:
                updates["name"] = name
            if emoji is not None:
                updates["emoji"] = emoji
            if description is not None:
                updates["description"] = description
            if is_active is not None:
                updates["is_active"] = is_active
            
            if updates:
                stmt = update(ShopCategory).where(ShopCategory.id == category_id).values(**updates)
                await session.execute(stmt)
                await session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating category: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def delete_category(category_id: int, session: AsyncSession | Session) -> bool:
        """Delete category (cascades to subcategories and products)"""
        try:
            stmt = delete(ShopCategory).where(ShopCategory.id == category_id)
            await session.execute(stmt)
            await session.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting category: {e}")
            await session.rollback()
            return False
    
    # ===== SUBCATEGORIES =====
    
    @staticmethod
    async def get_subcategories_by_category(category_id: int, session: AsyncSession | Session, 
                                           active_only: bool = True) -> List[ShopSubcategory]:
        """Get all subcategories for a category"""
        try:
            stmt = select(ShopSubcategory).where(
                ShopSubcategory.category_id == category_id
            ).order_by(ShopSubcategory.sort_order, ShopSubcategory.name)
            
            if active_only:
                stmt = stmt.where(ShopSubcategory.is_active == True)
            
            result = await session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting subcategories: {e}")
            return []
    
    @staticmethod
    async def get_subcategory_by_id(subcategory_id: int, session: AsyncSession | Session) -> Optional[ShopSubcategory]:
        """Get subcategory by ID"""
        try:
            stmt = select(ShopSubcategory).where(ShopSubcategory.id == subcategory_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting subcategory: {e}")
            return None
    
    @staticmethod
    async def create_subcategory(category_id: int, name: str, emoji: str, 
                                description: str, session: AsyncSession | Session) -> Optional[ShopSubcategory]:
        """Create new subcategory"""
        try:
            subcategory = ShopSubcategory(
                category_id=category_id,
                name=name,
                emoji=emoji,
                description=description,
                is_active=True
            )
            session.add(subcategory)
            await session.commit()
            await session.refresh(subcategory)
            return subcategory
        except Exception as e:
            logger.error(f"Error creating subcategory: {e}")
            await session.rollback()
            return None
    
    @staticmethod
    async def update_subcategory(subcategory_id: int, name: str = None, emoji: str = None,
                                description: str = None, is_active: bool = None,
                                session: AsyncSession | Session = None) -> bool:
        """Update subcategory"""
        try:
            updates = {}
            if name is not None:
                updates["name"] = name
            if emoji is not None:
                updates["emoji"] = emoji
            if description is not None:
                updates["description"] = description
            if is_active is not None:
                updates["is_active"] = is_active
            
            if updates:
                stmt = update(ShopSubcategory).where(ShopSubcategory.id == subcategory_id).values(**updates)
                await session.execute(stmt)
                await session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating subcategory: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def delete_subcategory(subcategory_id: int, session: AsyncSession | Session) -> bool:
        """Delete subcategory (cascades to products)"""
        try:
            stmt = delete(ShopSubcategory).where(ShopSubcategory.id == subcategory_id)
            await session.execute(stmt)
            await session.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting subcategory: {e}")
            await session.rollback()
            return False
    
    # ===== PRODUCTS =====
    
    @staticmethod
    async def get_products_by_subcategory(subcategory_id: int, session: AsyncSession | Session,
                                         active_only: bool = True) -> List[ShopProduct]:
        """Get all products for a subcategory"""
        try:
            stmt = select(ShopProduct).where(
                ShopProduct.subcategory_id == subcategory_id
            ).order_by(ShopProduct.sort_order, ShopProduct.name)
            
            if active_only:
                stmt = stmt.where(ShopProduct.is_active == True)
            
            result = await session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return []
    
    @staticmethod
    async def get_product_by_id(product_id: int, session: AsyncSession | Session) -> Optional[ShopProduct]:
        """Get product by ID"""
        try:
            stmt = select(ShopProduct).where(ShopProduct.id == product_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting product: {e}")
            return None
    
    @staticmethod
    async def create_product(subcategory_id: int, name: str, emoji: str, description: str,
                           price_per_unit: float, unit: str, min_quantity: int,
                           max_quantity: int, session: AsyncSession | Session) -> Optional[ShopProduct]:
        """Create new product"""
        try:
            product = ShopProduct(
                subcategory_id=subcategory_id,
                name=name,
                emoji=emoji,
                description=description,
                price_per_unit=price_per_unit,
                unit=unit,
                min_quantity=min_quantity,
                max_quantity=max_quantity,
                is_active=True,
                in_stock=True
            )
            session.add(product)
            await session.commit()
            await session.refresh(product)
            return product
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            await session.rollback()
            return None
    
    @staticmethod
    async def update_product(product_id: int, name: str = None, emoji: str = None,
                           description: str = None, price_per_unit: float = None,
                           unit: str = None, min_quantity: int = None, max_quantity: int = None,
                           is_active: bool = None, in_stock: bool = None,
                           session: AsyncSession | Session = None) -> bool:
        """Update product"""
        try:
            updates = {}
            if name is not None:
                updates["name"] = name
            if emoji is not None:
                updates["emoji"] = emoji
            if description is not None:
                updates["description"] = description
            if price_per_unit is not None:
                updates["price_per_unit"] = price_per_unit
            if unit is not None:
                updates["unit"] = unit
            if min_quantity is not None:
                updates["min_quantity"] = min_quantity
            if max_quantity is not None:
                updates["max_quantity"] = max_quantity
            if is_active is not None:
                updates["is_active"] = is_active
            if in_stock is not None:
                updates["in_stock"] = in_stock
            
            if updates:
                stmt = update(ShopProduct).where(ShopProduct.id == product_id).values(**updates)
                await session.execute(stmt)
                await session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating product: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def delete_product(product_id: int, session: AsyncSession | Session) -> bool:
        """Delete product"""
        try:
            stmt = delete(ShopProduct).where(ShopProduct.id == product_id)
            await session.execute(stmt)
            await session.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting product: {e}")
            await session.rollback()
            return False
    
    # ===== SETTINGS =====
    
    @staticmethod
    async def get_setting(key: str, session: AsyncSession | Session, default: str = None) -> Optional[str]:
        """Get setting value"""
        try:
            stmt = select(ShopSettings).where(ShopSettings.setting_key == key)
            result = await session.execute(stmt)
            setting = result.scalar_one_or_none()
            return setting.setting_value if setting else default
        except Exception as e:
            logger.error(f"Error getting setting: {e}")
            return default
    
    @staticmethod
    async def set_setting(key: str, value: str, description: str = None, 
                         session: AsyncSession | Session = None) -> bool:
        """Set or update setting"""
        try:
            stmt = select(ShopSettings).where(ShopSettings.setting_key == key)
            result = await session.execute(stmt)
            setting = result.scalar_one_or_none()
            
            if setting:
                setting.setting_value = value
                if description:
                    setting.description = description
            else:
                setting = ShopSettings(
                    setting_key=key,
                    setting_value=value,
                    description=description
                )
                session.add(setting)
            
            await session.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting value: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def initialize_default_settings(session: AsyncSession | Session) -> bool:
        """Initialize default settings if not exist"""
        try:
            for key, value in DEFAULT_SHOP_SETTINGS.items():
                existing = await ShopService.get_setting(key, session)
                if existing is None:
                    await ShopService.set_setting(key, value, f"Default {key}", session)
            return True
        except Exception as e:
            logger.error(f"Error initializing settings: {e}")
            return False
