from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./hh_auto_apply.db"
    
    # HH.ru OAuth
    hh_client_id: Optional[str] = None
    hh_client_secret: Optional[str] = None
    hh_redirect_uri: str = "http://localhost:8000/oauth/callback"
    hh_user_agent: str = "HH.ru Auto Apply/1.0 (auto-apply@example.com)"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Application settings
    check_interval_minutes: int = 30  # Интервал проверки новых вакансий
    max_applications_per_day: int = 50  # Максимум откликов в день
    max_users: int = 100  # Максимум пользователей
    
    class Config:
        env_file = ".env"


settings = Settings() 