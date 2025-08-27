import asyncio
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from app.database import JobSearch, Application, RequestLog, SystemSettings
from app.types import JobSearchCreate, HHApplicationRequest
from app.config import settings
from app.database import AsyncSessionLocal


class AutoApplyService:
    def __init__(self):
        self.is_running = False
        self.task = None
    
    async def create_job_search(self, session: AsyncSession, job_data: JobSearchCreate, user_id: int) -> JobSearch:
        """Создание нового поиска работы"""
        from app.database import JobSearch
        
        job_search = JobSearch(
            user_id=user_id,
            name=job_data.name,
            search_params=job_data.search_params.dict(),
            cover_letter=job_data.cover_letter,
            is_active=True
        )
        session.add(job_search)
        await session.commit()
        await session.refresh(job_search)
        return job_search
    
    async def get_job_searches(self, session: AsyncSession, user_id: int) -> List[JobSearch]:
        """Получение активных поисков работы пользователя"""
        from app.database import JobSearch
        result = await session.execute(
            select(JobSearch).where(
                JobSearch.is_active == True,
                JobSearch.user_id == user_id
            )
        )
        return result.scalars().all()
    
    async def get_applications(self, session: AsyncSession, user_id: int, job_search_id: Optional[int] = None) -> List[Application]:
        """Получение откликов пользователя"""
        from app.database import Application
        query = select(Application).where(Application.user_id == user_id)
        if job_search_id:
            query = query.where(Application.job_search_id == job_search_id)
        query = query.order_by(Application.applied_at.desc())
        
        result = await session.execute(query)
        return result.scalars().all()
    

    
    async def check_already_applied(self, session: AsyncSession, vacancy_id: str, user_id: int) -> bool:
        """Проверка, был ли уже отклик на эту вакансию"""
        from app.database import Application
        result = await session.execute(
            select(Application).where(
                Application.vacancy_id == vacancy_id,
                Application.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def save_application(self, session: AsyncSession, job_search_id: int, user_id: int, vacancy_id: str, 
                             vacancy_title: str, company_name: str, status: str = "pending") -> Application:
        """Сохранение отклика в базу данных"""
        from app.database import Application
        application = Application(
            user_id=user_id,
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
                         user_id: int = None, job_search_id: int = None, details: str = None, error_message: str = None):
        """Логирование запросов к API"""
        from app.database import RequestLog
        log_entry = RequestLog(
            user_id=user_id,
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
        
        # Получаем access token пользователя
        from app.database import HHUserCredentials
        result = await session.execute(
            select(HHUserCredentials).where(
                HHUserCredentials.user_id == job_search.user_id
            ).order_by(HHUserCredentials.created_at.desc()).limit(1)
        )
        credentials = result.scalar_one_or_none()
        
        if not credentials or not credentials.access_token:
            print(f"Нет валидного access token для пользователя {job_search.user_id}")
            await self.log_request(
                session, 
                "search_vacancies", 
                "no_token", 
                user_id=job_search.user_id,
                job_search_id=job_search.id, 
                details=f"Поиск: {job_search.name}"
            )
            return 0
        
        # Проверяем, не истек ли токен
        if credentials.expires_at and credentials.expires_at <= datetime.now():
            print(f"Токен истек для пользователя {job_search.user_id}")
            await self.log_request(
                session,
                "search_vacancies",
                "token_expired",
                user_id=job_search.user_id,
                job_search_id=job_search.id,
                details=f"Поиск: {job_search.name}"
            )
            return 0
        
        if not credentials.resume_id:
            print(f"Нет настроенного резюме для пользователя {job_search.user_id}")
            return 0
        
        try:
            # Ищем вакансии используя новые параметры API
            from app.utils.hh_api import hh_api_client
            vacancies_response = await hh_api_client.search_vacancies(
                job_search.search_params, 
                credentials.access_token
            )
            
            # Логируем успешный поиск
            await self.log_request(
                session,
                "search_vacancies",
                "success",
                user_id=job_search.user_id,
                job_search_id=job_search.id,
                details=f"Найдено вакансий: {len(vacancies_response.items)}, Поиск: {job_search.name}"
            )
            
            for vacancy in vacancies_response.items:
                # Проверяем, не откликались ли уже
                if await self.check_already_applied(session, vacancy.id, job_search.user_id):
                    continue
                
                # Проверяем лимит откликов в день для пользователя
                today_applications = await session.execute(
                    select(Application).where(
                        and_(
                            Application.user_id == job_search.user_id,
                            Application.applied_at >= datetime.now().date(),
                            Application.status == "success"
                        )
                    )
                )
                if today_applications.scalars().count() >= settings.max_applications_per_day:
                    print(f"Достигнут лимит откликов в день для пользователя {job_search.user_id}: {settings.max_applications_per_day}")
                    return applied_count
                
                try:
                    # Создаем отклик
                    from app.types import HHApplicationRequest
                    application_request = HHApplicationRequest(
                        resume_id=credentials.resume_id,
                        vacancy_id=vacancy.id,
                        message=job_search.cover_letter
                    )
                    
                    # Отправляем отклик
                    application_response = await hh_api_client.apply_to_vacancy(application_request, credentials.access_token)
                    
                    # Логируем успешный отклик
                    await self.log_request(
                        session,
                        "apply_vacancy",
                        "success",
                        user_id=job_search.user_id,
                        job_search_id=job_search.id,
                        details=f"Вакансия: {vacancy.name}, Компания: {vacancy.employer.get('name', 'Неизвестная компания')}"
                    )
                    
                    # Сохраняем в базу
                    await self.save_application(
                        session=session,
                        job_search_id=job_search.id,
                        user_id=job_search.user_id,
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
                        user_id=job_search.user_id,
                        job_search_id=job_search.id,
                        details=f"Вакансия: {vacancy.name}",
                        error_message=str(e)
                    )
                    
                    # Сохраняем неудачный отклик
                    await self.save_application(
                        session=session,
                        job_search_id=job_search.id,
                        user_id=job_search.user_id,
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
                async with AsyncSessionLocal() as session:
                    # Получаем всех пользователей с активными поисками
                    from app.database import User, JobSearch
                    from sqlalchemy import select
                    
                    # Получаем пользователей с активными поисками
                    result = await session.execute(
                        select(User.id).distinct().join(JobSearch).where(JobSearch.is_active == True)
                    )
                    user_ids = [row[0] for row in result.fetchall()]
                    
                    total_applied = 0
                    for user_id in user_ids:
                        # Получаем активные поиски для каждого пользователя
                        job_searches = await self.get_job_searches(session, user_id)
                        
                        for job_search in job_searches:
                            applied = await self.process_job_search(session, job_search)
                            total_applied += applied
                    
                    if total_applied > 0:
                        print(f"Обработано пользователей: {len(user_ids)}, откликов: {total_applied}")
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