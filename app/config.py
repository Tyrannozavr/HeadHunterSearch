from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./hh_auto_apply.db"
    
    # HH.ru API
    hh_client_id: Optional[str] = None
    hh_client_secret: Optional[str] = None
    hh_api_base_url: str = "https://api.hh.ru"
    
    # Application settings
    check_interval_minutes: int = 30  # Интервал проверки новых вакансий
    max_applications_per_day: int = 50  # Максимум откликов в день
    
    class Config:
        env_file = ".env"


settings = Settings() 