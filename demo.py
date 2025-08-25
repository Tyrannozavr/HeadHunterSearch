#!/usr/bin/env python3
"""
Демонстрационный скрипт для работы с API HH.ru Auto Apply
"""

import requests
import json
import time
from typing import Dict, Any


class HHAPIDemo:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса системы"""
        response = self.session.get(f"{self.base_url}/api/status")
        return response.json()
    
    def save_credentials(self, access_token: str, resume_id: str = None) -> Dict[str, Any]:
        """Сохранение учетных данных"""
        data = {
            "access_token": access_token,
            "resume_id": resume_id
        }
        response = self.session.post(f"{self.base_url}/api/credentials", json=data)
        return response.json()
    
    def create_job_search(self, name: str, filter_url: str, cover_letter: str) -> Dict[str, Any]:
        """Создание поиска работы"""
        data = {
            "name": name,
            "filter_url": filter_url,
            "cover_letter": cover_letter
        }
        response = self.session.post(f"{self.base_url}/api/job-searches", json=data)
        return response.json()
    
    def get_job_searches(self) -> list:
        """Получение списка поисков работы"""
        response = self.session.get(f"{self.base_url}/api/job-searches")
        return response.json()
    
    def get_applications(self) -> list:
        """Получение списка откликов"""
        response = self.session.get(f"{self.base_url}/api/applications")
        return response.json()
    
    def test_connection(self) -> Dict[str, Any]:
        """Тест подключения к API HH.ru"""
        response = self.session.post(f"{self.base_url}/api/test-connection")
        return response.json()
    
    def start_auto_apply(self) -> Dict[str, Any]:
        """Запуск автоматического отклика"""
        response = self.session.post(f"{self.base_url}/api/start-auto-apply")
        return response.json()
    
    def stop_auto_apply(self) -> Dict[str, Any]:
        """Остановка автоматического отклика"""
        response = self.session.post(f"{self.base_url}/api/stop-auto-apply")
        return response.json()
    
    def run_single_check(self) -> Dict[str, Any]:
        """Однократная проверка вакансий"""
        response = self.session.post(f"{self.base_url}/api/run-single-check")
        return response.json()


def main():
    """Демонстрация работы с API"""
    print("🚀 Демонстрация работы с API HH.ru Auto Apply\n")
    
    api = HHAPIDemo()
    
    # 1. Проверка статуса
    print("1. 📊 Проверка статуса системы:")
    status = api.get_status()
    print(f"   Статус: {'Работает' if status['is_running'] else 'Остановлен'}")
    print(f"   Интервал проверки: {status['check_interval_minutes']} минут\n")
    
    # 2. Сохранение тестовых учетных данных
    print("2. 🔑 Сохранение тестовых учетных данных:")
    try:
        result = api.save_credentials(
            access_token="demo_token_12345",
            resume_id="demo_resume_67890"
        )
        print(f"   Результат: {result['message']}\n")
    except Exception as e:
        print(f"   Ошибка: {e}\n")
    
    # 3. Создание тестового поиска работы
    print("3. 🔍 Создание тестового поиска работы:")
    try:
        job_search = api.create_job_search(
            name="Демо поиск Python разработчика",
            filter_url="https://hh.ru/search/vacancy?text=python&area=1&experience=between1And3",
            cover_letter="Здравствуйте! Я заинтересован в вашей вакансии Python разработчика. Имею опыт работы с FastAPI, SQLAlchemy и современными технологиями. Готов обсудить возможности сотрудничества."
        )
        print(f"   Создан поиск с ID: {job_search['id']}")
        print(f"   Название: {job_search['name']}\n")
    except Exception as e:
        print(f"   Ошибка: {e}\n")
    
    # 4. Получение списка поисков
    print("4. 📋 Список активных поисков:")
    try:
        searches = api.get_job_searches()
        for search in searches:
            print(f"   - {search['name']} (ID: {search['id']})")
        print()
    except Exception as e:
        print(f"   Ошибка: {e}\n")
    
    # 5. Получение списка откликов
    print("5. 📝 Список откликов:")
    try:
        applications = api.get_applications()
        if applications:
            for app in applications[:3]:  # Показываем только первые 3
                print(f"   - {app['vacancy_title']} в {app['company_name']} ({app['status']})")
        else:
            print("   Откликов пока нет")
        print()
    except Exception as e:
        print(f"   Ошибка: {e}\n")
    
    # 6. Тест подключения (без реального токена)
    print("6. 🔌 Тест подключения к API HH.ru:")
    try:
        result = api.test_connection()
        print(f"   Результат: {result.get('detail', 'Ошибка')}")
        print("   (Ожидается ошибка, так как используется тестовый токен)\n")
    except Exception as e:
        print(f"   Ошибка: {e}\n")
    
    # 7. Демонстрация управления автоматическим откликом
    print("7. ⚙️ Управление автоматическим откликом:")
    
    # Запуск
    try:
        result = api.start_auto_apply()
        print(f"   Запуск: {result['message']}")
    except Exception as e:
        print(f"   Ошибка запуска: {e}")
    
    time.sleep(1)
    
    # Проверка статуса
    status = api.get_status()
    print(f"   Статус после запуска: {'Работает' if status['is_running'] else 'Остановлен'}")
    
    # Остановка
    try:
        result = api.stop_auto_apply()
        print(f"   Остановка: {result['message']}")
    except Exception as e:
        print(f"   Ошибка остановки: {e}")
    
    print()
    
    # 8. Однократная проверка
    print("8. 🔍 Однократная проверка вакансий:")
    try:
        result = api.run_single_check()
        print(f"   Результат: {result['message']}")
        print(f"   Обработано поисков: {result['job_searches_processed']}")
        print(f"   Отправлено откликов: {result['applications_sent']}")
    except Exception as e:
        print(f"   Ошибка: {e}")
    
    print("\n" + "="*60)
    print("🎉 Демонстрация завершена!")
    print("\n📝 Для реального использования:")
    print("1. Получите Access Token на https://dev.hh.ru/admin")
    print("2. Найдите ID вашего резюме")
    print("3. Скопируйте ссылку с фильтрами поиска на HH.ru")
    print("4. Настройте сопроводительное письмо")
    print("5. Запустите автоматический отклик")
    print("\n🌐 Веб-интерфейс доступен по адресу: http://localhost:8000")


if __name__ == "__main__":
    main() 