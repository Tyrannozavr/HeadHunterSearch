import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.database import init_db, AsyncSessionLocal
from app.services import auto_apply_service
from app.utils.auth import get_password_hash
from app.database import User, SystemSettings
from sqlalchemy import select

async def migrate_database():
    print("🔄 Начинаю миграцию базы данных...")
    
    try:
        # Удаляем старые таблицы и создаем новые
        from app.database import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            # Удаляем все таблицы
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("DROP TABLE IF EXISTS job_searches")))
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("DROP TABLE IF EXISTS applications")))
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("DROP TABLE IF EXISTS hh_user_credentials")))
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("DROP TABLE IF EXISTS request_logs")))
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("DROP TABLE IF EXISTS system_settings")))
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("DROP TABLE IF EXISTS oauth_states")))
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("DROP TABLE IF EXISTS users")))
            print("🗑️ Старые таблицы удалены")
        
        # Инициализируем новую структуру базы
        await init_db()
        print("✅ Новая структура базы данных создана")
        
        async with AsyncSessionLocal() as session:
            # Создаем администратора по умолчанию
            admin_exists = await session.execute(
                select(User).where(User.username == "admin")
            )
            
            if not admin_exists.scalar_one_or_none():
                admin_user = User(
                    username="admin",
                    email="admin@example.com",
                    hashed_password=get_password_hash("admin123"),
                    role="admin",
                    is_active=True
                )
                session.add(admin_user)
                await session.commit()
                print("✅ Администратор создан (логин: admin, пароль: admin123)")
            else:
                print("ℹ️ Администратор уже существует")
            
            # Устанавливаем начальные настройки системы
            await auto_apply_service.update_setting(
                session, 
                "check_interval_minutes", 
                "30", 
                "Интервал проверки новых вакансий в минутах"
            )
            await auto_apply_service.update_setting(
                session, 
                "max_applications_per_day", 
                "50", 
                "Максимальное количество откликов в день"
            )
            await auto_apply_service.update_setting(
                session, 
                "max_users", 
                "100", 
                "Максимальное количество пользователей"
            )
            print("✅ Начальные настройки системы установлены")
        
        print("🎉 Миграция базы данных завершена успешно!")
        print("\n📝 Следующие шаги:")
        print("1. Запустите приложение: python main.py")
        print("2. Откройте http://localhost:8000/register")
        print("3. Создайте аккаунт или войдите как admin/admin123")
        print("4. Подключите HH.ru через OAuth")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(migrate_database()) 