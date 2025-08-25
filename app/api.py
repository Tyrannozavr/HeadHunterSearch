from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import os

from app.database import get_db, init_db
from app.models import JobSearchCreate, JobSearchResponse, ApplicationResponse, UserCredentialsCreate
from app.services import auto_apply_service
from app.hh_api import hh_client


app = FastAPI(title="HH.ru Auto Apply", description="Автоматический отклик на вакансии через API HH.ru")

# Подключаем шаблоны
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    await init_db()
    print("База данных инициализирована")


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при завершении"""
    await hh_client.close()
    auto_apply_service.stop_auto_apply()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница с формой"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/credentials", response_model=dict)
async def save_credentials(
    credentials: UserCredentialsCreate,
    session: AsyncSession = Depends(get_db)
):
    """Сохранение учетных данных пользователя"""
    try:
        await auto_apply_service.save_credentials(
            session=session,
            access_token=credentials.access_token,
            refresh_token=credentials.refresh_token,
            resume_id=credentials.resume_id
        )
        return {"message": "Учетные данные сохранены"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/job-searches", response_model=JobSearchResponse)
async def create_job_search(
    job_search: JobSearchCreate,
    session: AsyncSession = Depends(get_db)
):
    """Создание нового поиска работы"""
    try:
        # Валидируем URL
        hh_client.extract_filters_from_url(job_search.filter_url)
        
        result = await auto_apply_service.create_job_search(session, job_search)
        return JobSearchResponse.from_orm(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/job-searches", response_model=List[JobSearchResponse])
async def get_job_searches(session: AsyncSession = Depends(get_db)):
    """Получение всех поисков работы"""
    try:
        job_searches = await auto_apply_service.get_job_searches(session)
        return [JobSearchResponse.from_orm(js) for js in job_searches]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/applications", response_model=List[ApplicationResponse])
async def get_applications(
    job_search_id: int = None,
    session: AsyncSession = Depends(get_db)
):
    """Получение откликов"""
    try:
        applications = await auto_apply_service.get_applications(session, job_search_id)
        return [ApplicationResponse.from_orm(app) for app in applications]
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
async def test_connection(session: AsyncSession = Depends(get_db)):
    """Тестирование подключения к API HH.ru"""
    try:
        access_token = await hh_client.get_access_token(session)
        if not access_token:
            raise HTTPException(status_code=400, detail="Нет валидного access token")
        
        # Пробуем получить резюме пользователя
        resumes = await hh_client.get_user_resumes(access_token)
        return {
            "status": "success",
            "message": "Подключение к API HH.ru успешно",
            "resumes_count": len(resumes)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка подключения: {str(e)}")


@app.post("/api/run-single-check")
async def run_single_check(background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_db)):
    """Запуск однократной проверки вакансий"""
    try:
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            job_searches = await auto_apply_service.get_job_searches(session)
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