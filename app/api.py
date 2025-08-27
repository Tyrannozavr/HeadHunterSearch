from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime
import os

from app.database import get_db, init_db
from app.types import JobSearchCreate, JobSearchResponse, ApplicationResponse
from app.services import auto_apply_service
from app.utils.hh_api import hh_api_client
from app.utils.auth import get_current_user
from app.auth import router as auth_router
from app.oauth import router as oauth_router


app = FastAPI(title="HH.ru Auto Apply", description="Автоматический отклик на вакансии через API HH.ru")

# Подключаем шаблоны
templates = Jinja2Templates(directory="templates")

# Подключаем роутеры
app.include_router(auth_router)
app.include_router(oauth_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    await init_db()
    print("База данных инициализирована")


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при завершении"""
    await hh_api_client.close()
    auto_apply_service.stop_auto_apply()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница с формой"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Страница регистрации"""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/statistics", response_class=HTMLResponse)
async def statistics(request: Request):
    """Страница детальной статистики"""
    return templates.TemplateResponse("statistics.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Страница настроек системы"""
    return templates.TemplateResponse("settings.html", {"request": request})





@app.post("/api/job-searches", response_model=JobSearchResponse)
async def create_job_search(
    job_search: JobSearchCreate,
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Создание нового поиска работы"""
    try:
        # Создаем поиск с привязкой к пользователю
        result = await auto_apply_service.create_job_search(
            session, 
            job_search, 
            current_user_id
        )
        return JobSearchResponse.from_orm(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/job-searches", response_model=List[JobSearchResponse])
async def get_job_searches(
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Получение поисков работы текущего пользователя"""
    try:
        job_searches = await auto_apply_service.get_job_searches(session, current_user_id)
        return [JobSearchResponse.from_orm(js) for js in job_searches]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/applications", response_model=List[ApplicationResponse])
async def get_applications(
    current_user_id: int = Depends(get_current_user),
    job_search_id: int = None,
    session: AsyncSession = Depends(get_db)
):
    """Получение откликов текущего пользователя"""
    try:
        applications = await auto_apply_service.get_applications(session, current_user_id, job_search_id)
        return [ApplicationResponse.from_orm(app) for app in applications]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/job-searches/{job_search_id}/deactivate")
async def deactivate_job_search(
    job_search_id: int, 
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Деактивация поиска работы"""
    try:
        from sqlalchemy import select
        from app.database import JobSearch
        
        result = await session.execute(
            select(JobSearch).where(
                JobSearch.id == job_search_id,
                JobSearch.user_id == current_user_id
            )
        )
        job_search = result.scalar_one_or_none()
        
        if not job_search:
            raise HTTPException(status_code=404, detail="Поиск не найден")
        
        job_search.is_active = False
        await session.commit()
        
        return {"message": "Поиск деактивирован"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/start-auto-apply")
async def start_auto_apply():
    """Запуск автоматического отклика"""
    try:
        auto_apply_service.start_auto_apply()
        return {"message": "Автоматический отклик запущен"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stop-auto-apply")
async def stop_auto_apply():
    """Остановка автоматического отклика"""
    try:
        auto_apply_service.stop_auto_apply()
        return {"message": "Автоматический отклик остановлен"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Получение статуса автоматического отклика"""
    return {
        "is_running": auto_apply_service.is_running,
        "check_interval_minutes": auto_apply_service.check_interval_minutes if hasattr(auto_apply_service, 'check_interval_minutes') else 30
    }


@app.post("/api/test-connection")
async def test_connection(
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Тестирование подключения к API HH.ru"""
    try:
        # Получаем токен текущего пользователя
        from sqlalchemy import select
        from app.database import HHUserCredentials
        
        result = await session.execute(
            select(HHUserCredentials).where(
                HHUserCredentials.user_id == current_user_id
            ).order_by(HHUserCredentials.created_at.desc()).limit(1)
        )
        credentials = result.scalar_one_or_none()
        
        if not credentials or not credentials.access_token:
            # Логируем отсутствие токена
            await auto_apply_service.log_request(
                session,
                "test_connection",
                "no_token",
                user_id=current_user_id,
                details="Попытка тестирования подключения без токена"
            )
            raise HTTPException(status_code=400, detail="Нет валидного access token")
        
        # Проверяем, не истек ли токен
        if credentials.expires_at and credentials.expires_at <= datetime.now():
            await auto_apply_service.log_request(
                session,
                "test_connection",
                "token_expired",
                user_id=current_user_id,
                details="Токен истек, требуется обновление"
            )
            raise HTTPException(status_code=400, detail="Токен истек, требуется обновление")
        
        # Пробуем получить резюме пользователя
        resumes = await hh_api_client.get_user_resumes(credentials.access_token)
        
        # Логируем успешное подключение
        await auto_apply_service.log_request(
            session,
            "test_connection",
            "success",
            user_id=current_user_id,
            details=f"Подключение успешно, найдено резюме: {len(resumes.items)}"
        )
        
        return {
            "status": "success",
            "message": "Подключение к API HH.ru успешно",
            "resumes_count": len(resumes.items)
        }
    except Exception as e:
        # Логируем ошибку подключения
        await auto_apply_service.log_request(
            session,
            "test_connection",
            "failed",
            user_id=current_user_id,
            details="Попытка тестирования подключения",
            error_message=str(e)
        )
        raise HTTPException(status_code=400, detail=f"Ошибка подключения: {str(e)}")


@app.post("/api/run-single-check")
async def run_single_check(
    background_tasks: BackgroundTasks, 
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Запуск однократной проверки вакансий"""
    try:
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            job_searches = await auto_apply_service.get_job_searches(session, current_user_id)
            total_applied = 0
            
            for job_search in job_searches:
                applied = await auto_apply_service.process_job_search(session, job_search)
                total_applied += applied
            
            return {
                "message": "Проверка завершена",
                "job_searches_processed": len(job_searches),
                "applications_sent": total_applied
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/request-logs")
async def get_request_logs(
    current_user_id: int = Depends(get_current_user),
    limit: int = 50,
    request_type: str = None,
    status: str = None,
    session: AsyncSession = Depends(get_db)
):
    """Получение логов запросов текущего пользователя"""
    try:
        from sqlalchemy import select, desc
        from app.database import RequestLog
        
        query = select(RequestLog).where(RequestLog.user_id == current_user_id).order_by(desc(RequestLog.created_at))
        
        if request_type:
            query = query.where(RequestLog.request_type == request_type)
        if status:
            query = query.where(RequestLog.status == status)
        
        query = query.limit(limit)
        result = await session.execute(query)
        logs = result.scalars().all()
        
        return [
            {
                "id": log.id,
                "user_id": log.user_id,
                "job_search_id": log.job_search_id,
                "request_type": log.request_type,
                "status": log.status,
                "details": log.details,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system-settings")
async def get_system_settings(
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Получение настроек системы"""
    try:
        settings_data = {
            "check_interval_minutes": await auto_apply_service.get_check_interval(session),
            "max_applications_per_day": await auto_apply_service.get_max_applications_per_day(session)
        }
        return settings_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/system-settings")
async def update_system_settings(
    request: Request,
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Обновление настроек системы"""
    try:
        # Получаем данные из body запроса
        body = await request.json()
        check_interval_minutes = body.get("check_interval_minutes")
        max_applications_per_day = body.get("max_applications_per_day")
        
        if check_interval_minutes is None or max_applications_per_day is None:
            raise HTTPException(status_code=400, detail="Отсутствуют обязательные параметры")
        
        await auto_apply_service.update_setting(
            session, 
            "check_interval_minutes", 
            str(check_interval_minutes),
            "Интервал проверки новых вакансий в минутах"
        )
        
        await auto_apply_service.update_setting(
            session, 
            "max_applications_per_day", 
            str(max_applications_per_day),
            "Максимальное количество откликов в день"
        )
        
        return {"message": "Настройки обновлены"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 