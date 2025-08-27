from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """Роли пользователей"""
    ADMIN = "admin"
    USER = "user"


class OAuthState(BaseModel):
    """Состояние OAuth авторизации"""
    state: str
    user_id: int
    created_at: datetime


class HHUserAuth(BaseModel):
    """Данные авторизации пользователя HH.ru"""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"
    expires_at: Optional[datetime] = None


class HHVacancySearchParams(BaseModel):
    """Параметры поиска вакансий"""
    text: Optional[str] = None
    search_field: Optional[str] = None
    experience: Optional[str] = None
    employment: Optional[str] = None
    schedule: Optional[str] = None
    area: Optional[str] = None
    metro: Optional[str] = None
    professional_role: Optional[str] = None
    industry: Optional[str] = None
    employer_id: Optional[str] = None
    excluded_employer_id: Optional[str] = None
    currency: Optional[str] = None
    salary: Optional[int] = None
    only_with_salary: Optional[bool] = False
    period: Optional[int] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    order_by: Optional[str] = None
    page: int = 0
    per_page: int = 20


class HHVacancy(BaseModel):
    """Вакансия из API HH.ru"""
    id: str
    name: str
    alternate_url: str
    apply_alternate_url: str
    employer: Dict[str, Any]
    area: Dict[str, Any]
    salary: Optional[Dict[str, Any]] = None
    schedule: Optional[Dict[str, Any]] = None
    experience: Optional[Dict[str, Any]] = None
    employment: Optional[Dict[str, Any]] = None
    response_letter_required: bool
    created_at: str
    published_at: str
    archived: bool = False
    premium: bool = False


class HHVacancyResponse(BaseModel):
    """Ответ API поиска вакансий"""
    items: List[HHVacancy]
    found: int
    pages: int
    page: int
    per_page: int


class HHApplicationRequest(BaseModel):
    """Запрос на отклик на вакансию"""
    resume_id: str
    vacancy_id: str
    message: Optional[str] = None


class HHApplicationResponse(BaseModel):
    """Ответ на отклик на вакансию"""
    id: str
    status: str
    location: Optional[str] = None


class HHResume(BaseModel):
    """Резюме пользователя"""
    id: str
    title: str
    access_type: Dict[str, Any]
    updated_at: str
    created_at: str


class HHResumeResponse(BaseModel):
    """Ответ API списка резюме"""
    items: List[HHResume]


class UserCreate(BaseModel):
    """Создание пользователя"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.USER


class UserLogin(BaseModel):
    """Вход пользователя"""
    username: str
    password: str


class UserResponse(BaseModel):
    """Ответ с данными пользователя"""
    id: int
    username: str
    email: str
    role: UserRole
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True


class JobSearchCreate(BaseModel):
    """Создание поиска работы"""
    name: str = Field(..., min_length=1, max_length=200)
    search_params: HHVacancySearchParams
    cover_letter: str = Field(..., max_length=10000)
    is_active: bool = True


class JobSearchResponse(BaseModel):
    """Ответ с поиском работы"""
    id: int
    user_id: int
    name: str
    search_params: HHVacancySearchParams
    cover_letter: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ApplicationResponse(BaseModel):
    """Ответ с откликом"""
    id: int
    user_id: int
    job_search_id: int
    vacancy_id: str
    vacancy_title: str
    company_name: str
    applied_at: datetime
    status: str
    
    class Config:
        from_attributes = True


class SystemSettings(BaseModel):
    """Настройки системы"""
    check_interval_minutes: int = Field(30, ge=5, le=1440)
    max_applications_per_day: int = Field(50, ge=1, le=200)
    max_users: int = Field(100, ge=1, le=1000)


class RequestLogResponse(BaseModel):
    """Ответ с логом запроса"""
    id: int
    user_id: Optional[int] = None
    job_search_id: Optional[int] = None
    request_type: str
    status: str
    details: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True 