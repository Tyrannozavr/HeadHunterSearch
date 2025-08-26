import asyncio
import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db, AsyncSessionLocal
from app.services import auto_apply_service


async def initialize_database():
    """Инициализация базы данных с начальными настройками"""
    print("🔄 Инициализация базы данных...")
    
    # Создаем таблицы
    await init_db()
    print("✅ Таблицы созданы")
    
    # Инициализируем начальные настройки
    async with AsyncSessionLocal() as session:
        # Настройка интервала проверки
        await auto_apply_service.update_setting(
            session,
            "check_interval_minutes",
            "30",
            "Интервал проверки новых вакансий в минутах"
        )
        
        # Настройка лимита откликов
        await auto_apply_service.update_setting(
            session,
            "max_applications_per_day",
            "50",
            "Максимальное количество откликов в день"
        )
        
        print("✅ Начальные настройки установлены")
    
    print("🎉 База данных успешно инициализирована!")


if __name__ == "__main__":
    asyncio.run(initialize_database()) 