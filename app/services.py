import asyncio
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from app.database import JobSearch, Application, UserCredentials, RequestLog, SystemSettings
from app.models import JobSearchCreate, HHApplicationRequest
from app.hh_api import hh_client
from app.config import settings
from app.database import AsyncSessionLocal


class AutoApplyService:
    def __init__(self):
        self.is_running = False
        self.task = None
    
    async def create_job_search(self, session: AsyncSession, job_data: JobSearchCreate) -> JobSearch:
        """Создание нового поиска работы"""
        job_search = JobSearch(
            name=job_data.name,
            filter_url=job_data.filter_url,
            cover_letter=job_data.cover_letter,
            is_active=True
        )
        session.add(job_search)
        await session.commit()
        await session.refresh(job_search)
        return job_search
    
    async def get_job_searches(self, session: AsyncSession) -> List[JobSearch]:
        """Получение всех активных поисков работы"""
        result = await session.execute(select(JobSearch).where(JobSearch.is_active == True))
        return result.scalars().all()
    
    async def get_applications(self, session: AsyncSession, job_search_id: Optional[int] = None) -> List[Application]:
        """Получение откликов"""
        query = select(Application)
        if job_search_id:
            query = query.where(Application.job_search_id == job_search_id)
        query = query.order_by(Application.applied_at.desc())
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def save_credentials(self, session: AsyncSession, access_token: str, refresh_token: Optional[str] = None, resume_id: Optional[str] = None) -> UserCredentials:
        """Сохранение учетных данных пользователя"""
        credentials = UserCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            resume_id=resume_id,
            expires_at=datetime.now() + timedelta(hours=24)  # Токен на 24 часа
        )
        session.add(credentials)
        await session.commit()
        await session.refresh(credentials)
        return credentials
    
    async def check_already_applied(self, session: AsyncSession, vacancy_id: str) -> bool:
        """Проверка, был ли уже отклик на эту вакансию"""
        result = await session.execute(
            select(Application).where(Application.vacancy_id == vacancy_id)
        )
        return result.scalar_one_or_none() is not None
    
    async def save_application(self, session: AsyncSession, job_search_id: int, vacancy_id: str, 
                             vacancy_title: str, company_name: str, status: str = "pending") -> Application:
        """Сохранение отклика в базу данных"""
        application = Application(
            job_search_id=job_search_id,
            vacancy_id=vacancy_id,
            vacancy_title=vacancy_title,
            company_name=company_name,
            status=status
        )
        session.add(application)
        await session.commit()
        await session.refresh(application)
        return application

    async def log_request(self, session: AsyncSession, request_type: str, status: str, 
                         job_search_id: int = None, details: str = None, error_message: str = None):
        """Логирование запросов к API"""
        log_entry = RequestLog(
            job_search_id=job_search_id,
            request_type=request_type,
            status=status,
            details=details,
            error_message=error_message
        )
        session.add(log_entry)
        await session.commit()

    async def get_setting(self, session: AsyncSession, key: str, default_value: str) -> str:
        """Получение настройки системы"""
        result = await session.execute(
            select(SystemSettings).where(SystemSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else default_value

    async def update_setting(self, session: AsyncSession, key: str, value: str, description: str = None):
        """Обновление настройки системы"""
        result = await session.execute(
            select(SystemSettings).where(SystemSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = value
            if description:
                setting.description = description
        else:
            setting = SystemSettings(
                key=key,
                value=value,
                description=description
            )
            session.add(setting)
        
        await session.commit()

    async def get_check_interval(self, session: AsyncSession) -> int:
        """Получение интервала проверки в минутах"""
        interval_str = await self.get_setting(session, "check_interval_minutes", str(settings.check_interval_minutes))
        return int(interval_str)

    async def get_max_applications_per_day(self, session: AsyncSession) -> int:
        """Получение максимального количества откликов в день"""
        max_app_str = await self.get_setting(session, "max_applications_per_day", str(settings.max_applications_per_day))
        return int(max_app_str)
    
    async def process_job_search(self, session: AsyncSession, job_search: JobSearch) -> int:
        """Обработка одного поиска работы - поиск и отклик на вакансии"""
        applied_count = 0
        
        # Получаем access token
        access_token = await hh_client.get_access_token(session)
        if not access_token:
            print("Нет валидного access token")
            await self.log_request(
                session, 
                "search_vacancies", 
                "no_token", 
                job_search.id, 
                f"Поиск: {job_search.name}"
            )
            return 0
        
        # Получаем резюме пользователя
        credentials_result = await session.execute(
            select(UserCredentials).order_by(UserCredentials.id.desc()).limit(1)
        )
        credentials = credentials_result.scalar_one_or_none()
        if not credentials or not credentials.resume_id:
            print("Нет настроенного резюме")
            return 0
        
        try:
            # Ищем вакансии
            vacancies_response = await hh_client.search_vacancies(job_search.filter_url, access_token)
            
            # Логируем успешный поиск
            await self.log_request(
                session,
                "search_vacancies",
                "success",
                job_search.id,
                f"Найдено вакансий: {len(vacancies_response.items)}, Поиск: {job_search.name}"
            )
            
            for vacancy in vacancies_response.items:
                # Проверяем, не откликались ли уже
                if await self.check_already_applied(session, vacancy.id):
                    continue
                
                # Проверяем лимит откликов в день
                today_applications = await session.execute(
                    select(Application).where(
                        and_(
                            Application.applied_at >= datetime.now().date(),
                            Application.status == "success"
                        )
                    )
                )
                if today_applications.scalars().count() >= settings.max_applications_per_day:
                    print(f"Достигнут лимит откликов в день: {settings.max_applications_per_day}")
                    return applied_count
                
                try:
                    # Создаем отклик
                    application_request = HHApplicationRequest(
                        resume_id=credentials.resume_id,
                        vacancy_id=vacancy.id,
                        message=job_search.cover_letter
                    )
                    
                    # Отправляем отклик
                    application_response = await hh_client.apply_to_vacancy(application_request, access_token)
                    
                    # Логируем успешный отклик
                    await self.log_request(
                        session,
                        "apply_vacancy",
                        "success",
                        job_search.id,
                        f"Вакансия: {vacancy.name}, Компания: {vacancy.employer.get('name', 'Неизвестная компания')}"
                    )
                    
                    # Сохраняем в базу
                    await self.save_application(
                        session=session,
                        job_search_id=job_search.id,
                        vacancy_id=vacancy.id,
                        vacancy_title=vacancy.name,
                        company_name=vacancy.employer.get("name", "Неизвестная компания"),
                        status="success"
                    )
                    
                    applied_count += 1
                    print(f"Успешно откликнулись на вакансию: {vacancy.name}")
                    
                    # Пауза между откликами
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    print(f"Ошибка отклика на вакансию {vacancy.id}: {e}")
                    
                    # Логируем ошибку отклика
                    await self.log_request(
                        session,
                        "apply_vacancy",
                        "failed",
                        job_search.id,
                        f"Вакансия: {vacancy.name}",
                        str(e)
                    )
                    
                    # Сохраняем неудачный отклик
                    await self.save_application(
                        session=session,
                        job_search_id=job_search.id,
                        vacancy_id=vacancy.id,
                        vacancy_title=vacancy.name,
                        company_name=vacancy.employer.get("name", "Неизвестная компания"),
                        status="failed"
                    )
        
        except Exception as e:
            print(f"Ошибка обработки поиска работы {job_search.id}: {e}")
        
        return applied_count
    
    async def run_auto_apply_loop(self):
        """Основной цикл автоматического отклика"""
        self.is_running = True
        print("Запущен автоматический отклик на вакансии")
        
        while self.is_running:
            try:
                async with hh_client.client:
                    async with AsyncSessionLocal() as session:
                        # Получаем все активные поиски
                        job_searches = await self.get_job_searches(session)
                        
                        total_applied = 0
                        for job_search in job_searches:
                            applied = await self.process_job_search(session, job_search)
                            total_applied += applied
                        
                        if total_applied > 0:
                            print(f"Обработано поисков: {len(job_searches)}, откликов: {total_applied}")
                        else:
                            print("Новых вакансий для отклика не найдено")
                
                # Получаем настраиваемый интервал
                check_interval = await self.get_check_interval(session)
                
                # Ждем следующего цикла
                await asyncio.sleep(check_interval * 60)
                
            except Exception as e:
                print(f"Ошибка в цикле автоматического отклика: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут при ошибке
    
    def start_auto_apply(self):
        """Запуск автоматического отклика в фоне"""
        if not self.is_running:
            self.task = asyncio.create_task(self.run_auto_apply_loop())
    
    def stop_auto_apply(self):
        """Остановка автоматического отклика"""
        self.is_running = False
        if self.task:
            self.task.cancel()


# Глобальный экземпляр сервиса
auto_apply_service = AutoApplyService() 