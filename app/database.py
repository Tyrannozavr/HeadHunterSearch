from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.config import settings
from app.types import UserRole

# Создаем асинхронный движок базы данных
engine = create_async_engine(settings.database_url, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    job_searches = relationship("JobSearch", back_populates="user")
    applications = relationship("Application", back_populates="user")
    hh_credentials = relationship("HHUserCredentials", back_populates="user")
    request_logs = relationship("RequestLog", back_populates="user")


class JobSearch(Base):
    __tablename__ = "job_searches"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    search_params = Column(JSON, nullable=False)  # Параметры поиска в JSON
    cover_letter = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    user = relationship("User", back_populates="job_searches")
    applications = relationship("Application", back_populates="job_search")
    request_logs = relationship("RequestLog")


class Application(Base):
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_search_id = Column(Integer, ForeignKey("job_searches.id"), nullable=False)
    vacancy_id = Column(String, nullable=False)
    vacancy_title = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="pending")  # pending, success, failed
    
    # Связи
    user = relationship("User", back_populates="applications")
    job_search = relationship("JobSearch", back_populates="applications")


class HHUserCredentials(Base):
    __tablename__ = "hh_user_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    resume_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    user = relationship("User", back_populates="hh_credentials")


class RequestLog(Base):
    __tablename__ = "request_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null для системных запросов
    job_search_id = Column(Integer, ForeignKey("job_searches.id"), nullable=True)  # null для общих запросов
    request_type = Column(String, nullable=False)  # search_vacancies, apply_vacancy, test_connection
    status = Column(String, nullable=False)  # success, failed, no_token
    details = Column(Text, nullable=True)  # Детали запроса/ответа
    error_message = Column(Text, nullable=True)  # Сообщение об ошибке
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    user = relationship("User", back_populates="request_logs")
    job_search = relationship("JobSearch")


class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)  # check_interval_minutes, max_applications_per_day
    value = Column(String, nullable=False)  # Значение настройки
    description = Column(Text, nullable=True)  # Описание настройки
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OAuthState(Base):
    __tablename__ = "oauth_states"
    
    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    user = relationship("User")


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) 