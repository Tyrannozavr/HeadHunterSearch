import asyncio

import uvicorn

from app.database import init_db


async def main():
    """Главная функция для запуска приложения"""
    # Инициализируем базу данных
    await init_db()
    
    # Запускаем сервер
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    asyncio.run(main()) 