from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from app.config import settings

# Создаем асинхронный движок базы данных
engine = create_async_engine(settings.database_url, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class JobSearch(Base):
    __tablename__ = "job_searches"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    filter_url = Column(Text, nullable=False)  # URL с фильтрами
    cover_letter = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Application(Base):
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    job_search_id = Column(Integer, nullable=False)
    vacancy_id = Column(String, nullable=False)
    vacancy_title = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="pending")  # pending, success, failed


class UserCredentials(Base):
    __tablename__ = "user_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    resume_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RequestLog(Base):
    __tablename__ = "request_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_search_id = Column(Integer, nullable=True)  # null для общих запросов
    request_type = Column(String, nullable=False)  # search_vacancies, apply_vacancy, test_connection
    status = Column(String, nullable=False)  # success, failed, no_token
    details = Column(Text, nullable=True)  # Детали запроса/ответа
    error_message = Column(Text, nullable=True)  # Сообщение об ошибке
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)  # check_interval_minutes, max_applications_per_day
    value = Column(String, nullable=False)  # Значение настройки
    description = Column(Text, nullable=True)  # Описание настройки
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) 