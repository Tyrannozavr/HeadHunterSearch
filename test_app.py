#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности HH.ru Auto Apply
"""

import asyncio
import sys
import os

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db, AsyncSessionLocal
from app.services import auto_apply_service
from app.models import JobSearchCreate, UserCredentialsCreate
from app.hh_api import hh_client


async def test_database():
    """Тест базы данных"""
    print("🔍 Тестирование базы данных...")
    
    try:
        await init_db()
        print("✅ База данных инициализирована успешно")
        
        async with AsyncSessionLocal() as session:
            # Тест создания учетных данных
            credentials_data = UserCredentialsCreate(
                access_token="test_token_123",
                resume_id="test_resume_456"
            )
            
            credentials = await auto_apply_service.save_credentials(
                session=session,
                access_token=credentials_data.access_token,
                resume_id=credentials_data.resume_id
            )
            print(f"✅ Учетные данные созданы с ID: {credentials.id}")
            
            # Тест создания поиска работы
            job_search_data = JobSearchCreate(
                name="Тестовый поиск Python разработчика",
                filter_url="https://hh.ru/search/vacancy?text=python&area=1",
                cover_letter="Здравствуйте! Заинтересован в вашей вакансии..."
            )
            
            job_search = await auto_apply_service.create_job_search(
                session=session,
                job_data=job_search_data
            )
            print(f"✅ Поиск работы создан с ID: {job_search.id}")
            
            # Тест получения данных
            job_searches = await auto_apply_service.get_job_searches(session)
            print(f"✅ Найдено активных поисков: {len(job_searches)}")
            
            applications = await auto_apply_service.get_applications(session)
            print(f"✅ Найдено откликов: {len(applications)}")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования базы данных: {e}")
        return False
    
    return True


async def test_hh_api():
    """Тест API HH.ru (без реальных запросов)"""
    print("\n🔍 Тестирование API HH.ru...")
    
    try:
        # Тест парсинга URL
        test_url = "https://hh.ru/search/vacancy?text=python&area=1&experience=between1And3"
        filters = hh_client.extract_filters_from_url(test_url)
        print(f"✅ Парсинг URL успешен: {filters}")
        
        # Тест валидации URL
        try:
            hh_client.extract_filters_from_url("https://google.com")
            print("❌ Ошибка: URL с неправильным доменом должен вызывать исключение")
            return False
        except ValueError:
            print("✅ Валидация URL работает корректно")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования API: {e}")
        return False
    
    return True


async def test_services():
    """Тест сервисов"""
    print("\n🔍 Тестирование сервисов...")
    
    try:
        # Тест создания сервиса
        service = auto_apply_service
        print("✅ Сервис создан успешно")
        
        # Тест статуса
        print(f"✅ Статус сервиса: {'Работает' if service.is_running else 'Остановлен'}")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования сервисов: {e}")
        return False
    
    return True


async def main():
    """Главная функция тестирования"""
    print("🚀 Запуск тестирования HH.ru Auto Apply\n")
    
    tests = [
        ("База данных", test_database),
        ("API HH.ru", test_hh_api),
        ("Сервисы", test_services),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Критическая ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))
    
    # Вывод результатов
    print("\n" + "="*50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nИтого: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n🎉 Все тесты пройдены успешно! Приложение готово к использованию.")
        print("\n📝 Следующие шаги:")
        print("1. Запустите приложение: python main.py")
        print("2. Откройте браузер: http://localhost:8000")
        print("3. Настройте учетные данные HH.ru")
        print("4. Создайте поиск работы и запустите автоматический отклик")
    else:
        print("\n⚠️  Некоторые тесты не пройдены. Проверьте конфигурацию.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 