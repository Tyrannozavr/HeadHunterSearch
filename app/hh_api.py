import httpx
import asyncio
from typing import Optional, List
from urllib.parse import urlparse, parse_qs
from app.models import HHVacancyResponse, HHApplicationRequest, HHApplicationResponse
from app.config import settings
from app.database import UserCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta


class HHAPIClient:
    def __init__(self):
        self.base_url = settings.hh_api_base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        await self.client.aclose()
    
    async def get_access_token(self, session: AsyncSession) -> Optional[str]:
        """Получает актуальный access token из базы данных"""
        result = await session.execute(select(UserCredentials).order_by(UserCredentials.id.desc()).limit(1))
        credentials = result.scalar_one_or_none()
        
        if not credentials:
            return None
        
        # Проверяем, не истек ли токен
        if credentials.expires_at and credentials.expires_at < datetime.now():
            return None
        
        return credentials.access_token
    
    def extract_filters_from_url(self, filter_url: str) -> dict:
        """Извлекает параметры фильтров из URL HH.ru"""
        try:
            parsed = urlparse(filter_url)
            if 'hh.ru' not in parsed.netloc:
                raise ValueError("URL должен быть с сайта hh.ru")
            
            # Извлекаем параметры из query string
            params = parse_qs(parsed.query)
            
            # Преобразуем списки в строки
            filters = {}
            for key, value in params.items():
                if value:
                    filters[key] = value[0] if len(value) == 1 else value
            
            return filters
        except Exception as e:
            raise ValueError(f"Ошибка парсинга URL: {e}")
    
    async def search_vacancies(self, filter_url: str, access_token: str) -> HHVacancyResponse:
        """Поиск вакансий по фильтрам"""
        filters = self.extract_filters_from_url(filter_url)
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "HH-User-Agent"
        }
        
        # Добавляем базовые параметры
        params = {
            "per_page": 20,
            "page": 0
        }
        params.update(filters)
        
        try:
            response = await self.client.get(
                f"{self.base_url}/vacancies",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return HHVacancyResponse(**data)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limit - ждем и повторяем
                await asyncio.sleep(60)
                return await self.search_vacancies(filter_url, access_token)
            else:
                raise Exception(f"Ошибка API HH.ru: {e.response.status_code} - {e.response.text}")
    
    async def apply_to_vacancy(self, application: HHApplicationRequest, access_token: str) -> HHApplicationResponse:
        """Отклик на вакансию"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "HH-User-Agent"
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/applications",
                headers=headers,
                json=application.dict()
            )
            response.raise_for_status()
            
            data = response.json()
            return HHApplicationResponse(**data)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limit - ждем и повторяем
                await asyncio.sleep(60)
                return await self.apply_to_vacancy(application, access_token)
            else:
                raise Exception(f"Ошибка отклика на вакансию: {e.response.status_code} - {e.response.text}")
    
    async def get_user_resumes(self, access_token: str) -> List[dict]:
        """Получение списка резюме пользователя"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "HH-User-Agent"
        }
        
        try:
            response = await self.client.get(
                f"{self.base_url}/resumes/mine",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()["items"]
            
        except httpx.HTTPStatusError as e:
            raise Exception(f"Ошибка получения резюме: {e.response.status_code} - {e.response.text}")


# Глобальный экземпляр клиента
hh_client = HHAPIClient() 