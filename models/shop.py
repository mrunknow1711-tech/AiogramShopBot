"""
models/shop.py - Dynamische Shop-Struktur
Erstelle dieses File: models/shop.py

Struktur: Category → Subcategory → Product
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from db import Base


class ShopCategory(Base):
    """Hauptkategorien (z.B. Schuhe, Kleidung, etc.)"""
    __tablename__ = "shop_categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    emoji = Column(String(10), default="📁")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)  # Für Sortierung
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    subcategories = relationship("ShopSubcategory", back_populates="category", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Category(id={self.id}, name={self.name})>"


class ShopSubcategory(Base):
    """Subkategorien (z.B. Sneaker, Stiefel, etc.)"""
    __tablename__ = "shop_subcategories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("shop_categories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    emoji = Column(String(10), default="📂")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("ShopCategory", back_populates="subcategories")
    products = relationship("ShopProduct", back_populates="subcategory", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Subcategory(id={self.id}, name={self.name})>"


class ShopProduct(Base):
    """Produkte (z.B. Nike Air Max, Adidas Yeezy, etc.)"""
    __tablename__ = "shop_products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subcategory_id = Column(Integer, ForeignKey("shop_subcategories.id"), nullable=False)
    
    # Produkt-Info
    name = Column(String(200), nullable=False)
    emoji = Column(String(10), default="📦")
    description = Column(Text, nullable=True)
    
    # Preis & Einheit
    price_per_unit = Column(Float, nullable=False)
    unit = Column(String(20), default="Stück")  # g, kg, Stück, ml, etc.
    min_quantity = Column(Integer, default=1)
    max_quantity = Column(Integer, default=2000)
    
    # Status
    is_active = Column(Boolean, default=True)
    in_stock = Column(Boolean, default=True)
    stock_quantity = Column(Integer, nullable=True)  # Optional: Lagerbestand tracken
    
    # Metadata
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subcategory = relationship("ShopSubcategory", back_populates="products")
    
    def __repr__(self):
        return f"<Product(id={self.id}, name={self.name}, price={self.price_per_unit})>"


class ShopSettings(Base):
    """Globale Shop-Einstellungen"""
    __tablename__ = "shop_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False)
    setting_value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ShopSettings(key={self.setting_key}, value={self.setting_value})>"


# Standard-Settings die beim Setup erstellt werden:
DEFAULT_SHOP_SETTINGS = {
    "shipping_hausdrop_cost": "15.00",
    "shipping_hausdrop_enabled": "true",
    "shipping_packstation_cost": "15.00",
    "shipping_packstation_enabled": "true",
    "currency": "EUR",
    "currency_symbol": "€",
    "shop_enabled": "true",
    "min_order_value": "0.00",
    "free_shipping_threshold": "0.00",  # 0 = nie gratis
}
