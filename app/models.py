from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime


class JobSearchCreate(BaseModel):
    name: str
    filter_url: str
    cover_letter: str


class JobSearchResponse(BaseModel):
    id: int
    name: str
    filter_url: str
    cover_letter: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ApplicationResponse(BaseModel):
    id: int
    job_search_id: int
    vacancy_id: str
    vacancy_title: str
    company_name: str
    applied_at: datetime
    status: str
    
    class Config:
        from_attributes = True


class UserCredentialsCreate(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    resume_id: Optional[str] = None


class HHVacancy(BaseModel):
    id: str
    name: str
    employer: dict
    alternate_url: Optional[str] = None


class HHVacancyResponse(BaseModel):
    items: list[HHVacancy]
    found: int
    pages: int
    per_page: int
    page: int


class HHApplicationRequest(BaseModel):
    resume_id: str
    vacancy_id: str
    message: str


class HHApplicationResponse(BaseModel):
    id: str
    status: str 