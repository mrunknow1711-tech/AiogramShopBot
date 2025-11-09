"""
FÜGE DIESE CALLBACKS ZU DEINER callbacks.py HINZU
(am Ende der Datei, nach den bestehenden Callbacks)
"""

from enum import IntEnum
from aiogram.filters.callback_data import CallbackData


# ===== ADMIN SHOP MANAGEMENT CALLBACKS =====

class ShopManagementAction(IntEnum):
    """Actions für Shop-Management"""
    VIEW_CATEGORIES = 1
    ADD_CATEGORY = 2
    EDIT_CATEGORY = 3
    DELETE_CATEGORY = 4
    VIEW_SUBCATEGORIES = 5
    ADD_SUBCATEGORY = 6
    EDIT_SUBCATEGORY = 7
    DELETE_SUBCATEGORY = 8
    VIEW_PRODUCTS = 9
    ADD_PRODUCT = 10
    EDIT_PRODUCT = 11
    DELETE_PRODUCT = 12
    SETTINGS = 13


class AdminShopCallback(CallbackData, prefix="admin_shop"):
    """Callback für Admin Shop-Verwaltung"""
    level: int
    action: ShopManagementAction | None = None
    category_id: int = 0
    subcategory_id: int = 0
    product_id: int = 0
    page: int = 0
    confirmation: bool = False
    
    @staticmethod
    def create(level: int, action: ShopManagementAction = None, category_id: int = 0,
               subcategory_id: int = 0, product_id: int = 0, page: int = 0, 
               confirmation: bool = False):
        return AdminShopCallback(
            level=level,
            action=action,
            category_id=category_id,
            subcategory_id=subcategory_id,
            product_id=product_id,
            page=page,
            confirmation=confirmation
        )
