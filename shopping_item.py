from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# Базовый класс для всех моделей
Base = declarative_base()

class ShoppingItem(Base):
    """
    Модель для элемента списка покупок.
    """
    __tablename__ = "shopping_items"

    id = Column(Integer, primary_key=True, index=True)
    
    # Текст самого товара (например, "Молоко 1л")
    name = Column(String, index=True, nullable=False)
    
    # Чат, к которому относится список (для поддержки разных чатов, если потребуется)
    chat_id = Column(Integer, nullable=False)
    
    # Флаг, куплен ли товар
    is_purchased = Column(Boolean, default=False)
    
    # Дата добавления
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        status = "Куплено" if self.is_purchased else "Нужно купить"
        return f"<ShoppingItem(name='{self.name}', status='{status}')>"