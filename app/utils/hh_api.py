import httpx
import asyncio
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs
from app.types import (
    HHVacancySearchParams, 
    HHVacancyResponse, 
    HHApplicationRequest, 
    HHApplicationResponse,
    HHResumeResponse,
    HHVacancy
)
from app.config import settings


class HHAPIClient:
    """Клиент для работы с API HH.ru"""
    
    def __init__(self):
        self.api_url = "https://api.hh.ru"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        await self.client.aclose()
    
    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Получение заголовков для запросов"""
        return {
            "Authorization": f"Bearer {access_token}",
            "HH-User-Agent": settings.hh_user_agent,
            "Content-Type": "application/json"
        }
    
    def parse_search_url(self, search_url: str) -> HHVacancySearchParams:
        """Парсинг URL поиска вакансий в параметры API"""
        try:
            parsed = urlparse(search_url)
            if 'hh.ru' not in parsed.netloc:
                raise ValueError("URL должен быть с сайта hh.ru")
            
            # Извлекаем параметры из query string
            params = parse_qs(parsed.query)
            
            # Преобразуем в параметры API
            search_params = HHVacancySearchParams()
            
            # Базовые параметры
            if 'text' in params:
                search_params.text = params['text'][0]
            if 'area' in params:
                search_params.area = params['area'][0]
            if 'experience' in params:
                search_params.experience = params['experience'][0]
            if 'employment' in params:
                search_params.employment = params['employment'][0]
            if 'schedule' in params:
                search_params.schedule = params['schedule'][0]
            if 'metro' in params:
                search_params.metro = params['metro'][0]
            if 'professional_role' in params:
                search_params.professional_role = params['professional_role'][0]
            if 'industry' in params:
                search_params.industry = params['industry'][0]
            if 'employer_id' in params:
                search_params.employer_id = params['employer_id'][0]
            if 'excluded_employer_id' in params:
                search_params.excluded_employer_id = params['excluded_employer_id'][0]
            if 'currency' in params:
                search_params.currency = params['currency'][0]
            if 'salary' in params:
                search_params.salary = int(params['salary'][0])
            if 'only_with_salary' in params:
                search_params.only_with_salary = params['only_with_salary'][0].lower() == 'true'
            if 'period' in params:
                search_params.period = int(params['period'][0])
            if 'order_by' in params:
                search_params.order_by = params['order_by'][0]
            
            return search_params
            
        except Exception as e:
            raise ValueError(f"Ошибка парсинга URL: {e}")
    
    async def search_vacancies(self, search_params: HHVacancySearchParams, access_token: str) -> HHVacancyResponse:
        """Поиск вакансий по параметрам"""
        headers = self._get_headers(access_token)
        
        # Преобразуем параметры в query string
        params = search_params.dict(exclude_none=True)
        
        try:
            response = await self.client.get(
                f"{self.api_url}/vacancies",
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
                return await self.search_vacancies(search_params, access_token)
            else:
                raise Exception(f"Ошибка API HH.ru: {e.response.status_code} - {e.response.text}")
    
    async def apply_to_vacancy(self, application: HHApplicationRequest, access_token: str) -> HHApplicationResponse:
        """Отклик на вакансию"""
        headers = self._get_headers(access_token)
        
        # Для отклика используем multipart/form-data
        form_data = {
            "resume_id": application.resume_id,
            "vacancy_id": application.vacancy_id
        }
        
        if application.message:
            form_data["message"] = application.message
        
        try:
            response = await self.client.post(
                f"{self.api_url}/negotiations",
                data=form_data,
                headers=headers
            )
            
            if response.status_code == 201:
                # Успешный отклик
                location = response.headers.get("Location", "")
                return HHApplicationResponse(
                    id=location.split("/")[-1] if location else "unknown",
                    status="success",
                    location=location
                )
            elif response.status_code == 303:
                # Прямой отклик на внешний сайт
                location = response.headers.get("Location", "")
                return HHApplicationResponse(
                    id="external",
                    status="external",
                    location=location
                )
            else:
                response.raise_for_status()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limit - ждем и повторяем
                await asyncio.sleep(60)
                return await self.apply_to_vacancy(application, access_token)
            else:
                error_data = e.response.json() if e.response.content else {}
                raise Exception(f"Ошибка отклика на вакансию: {e.response.status_code} - {error_data}")
    
    async def get_user_resumes(self, access_token: str) -> HHResumeResponse:
        """Получение списка резюме пользователя"""
        headers = self._get_headers(access_token)
        
        try:
            response = await self.client.get(
                f"{self.api_url}/resumes/mine",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            return HHResumeResponse(**data)
            
        except httpx.HTTPStatusError as e:
            raise Exception(f"Ошибка получения резюме: {e.response.status_code} - {e.response.text}")
    
    async def get_vacancy_details(self, vacancy_id: str, access_token: str) -> HHVacancy:
        """Получение детальной информации о вакансии"""
        headers = self._get_headers(access_token)
        
        try:
            response = await self.client.get(
                f"{self.api_url}/vacancies/{vacancy_id}",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            return HHVacancy(**data)
            
        except httpx.HTTPStatusError as e:
            raise Exception(f"Ошибка получения вакансии: {e.response.status_code} - {e.response.text}")
    
    async def check_vacancy_application(self, vacancy_id: str, access_token: str) -> bool:
        """Проверка, откликался ли уже на вакансию"""
        headers = self._get_headers(access_token)
        
        try:
            response = await self.client.get(
                f"{self.api_url}/negotiations",
                headers=headers,
                params={"vacancy_id": vacancy_id}
            )
            
            if response.status_code == 200:
                data = response.json()
                return len(data.get("items", [])) > 0
            else:
                return False
                
        except Exception:
            return False


# Глобальный экземпляр API клиента
hh_api_client = HHAPIClient() 