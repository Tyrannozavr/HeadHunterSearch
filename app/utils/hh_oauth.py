import secrets
import hashlib
import time
from typing import Optional, Dict, Any
from urllib.parse import urlencode, parse_qs, urlparse
import httpx
from app.types import HHUserAuth, OAuthState
from app.config import settings


class HHOAuthClient:
    """Клиент для OAuth 2.0 авторизации с HH.ru"""
    
    def __init__(self):
        self.client_id = settings.hh_client_id or "test"
        self.client_secret = settings.hh_client_secret or "test"
        self.redirect_uri = settings.hh_redirect_uri
        self.base_url = "https://hh.ru"
        self.api_url = "https://api.hh.ru"
    
    def generate_authorization_url(self, user_id: int, state: Optional[str] = None) -> str:
        """Генерация URL для авторизации пользователя"""
        if not state:
            state = self._generate_state(user_id)
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "state": state,
            "redirect_uri": self.redirect_uri
        }
        
        return f"{self.base_url}/oauth/authorize?{urlencode(params)}"
    
    def _generate_state(self, user_id: int) -> str:
        """Генерация уникального state для безопасности"""
        timestamp = str(int(time.time()))
        random_part = secrets.token_urlsafe(16)
        user_hash = hashlib.sha256(f"{user_id}:{timestamp}".encode()).hexdigest()[:8]
        
        return f"{timestamp}_{random_part}_{user_hash}"
    
    def parse_authorization_code(self, url: str) -> Optional[Dict[str, str]]:
        """Парсинг authorization code из redirect URL"""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        if "error" in query_params:
            error = query_params["error"][0]
            if error == "access_denied":
                return {"error": "access_denied"}
            else:
                return {"error": error}
        
        if "code" not in query_params:
            return {"error": "no_code"}
        
        return {
            "code": query_params["code"][0],
            "state": query_params.get("state", [None])[0]
        }
    
    async def exchange_code_for_tokens(self, authorization_code: str) -> HHUserAuth:
        """Обмен authorization code на access и refresh токены"""
        async with httpx.AsyncClient() as client:
            data = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": authorization_code,
                "redirect_uri": self.redirect_uri
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": settings.hh_user_agent
            }
            
            response = await client.post(
                f"{self.api_url}/token",
                data=data,
                headers=headers
            )
            
            if response.status_code != 200:
                error_data = response.json()
                raise Exception(f"Ошибка получения токенов: {error_data}")
            
            token_data = response.json()
            
            # Вычисляем время истечения токена
            expires_at = None
            if "expires_in" in token_data:
                expires_at = time.time() + token_data["expires_in"]
            
            return HHUserAuth(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data["expires_in"],
                token_type=token_data.get("token_type", "bearer"),
                expires_at=expires_at
            )
    
    async def refresh_tokens(self, refresh_token: str) -> HHUserAuth:
        """Обновление access токена с помощью refresh токена"""
        async with httpx.AsyncClient() as client:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": settings.hh_user_agent
            }
            
            response = await client.post(
                f"{self.api_url}/token",
                data=data,
                headers=headers
            )
            
            if response.status_code != 200:
                error_data = response.json()
                raise Exception(f"Ошибка обновления токенов: {error_data}")
            
            token_data = response.json()
            
            # Вычисляем время истечения токена
            expires_at = None
            if "expires_in" in token_data:
                expires_at = time.time() + token_data["expires_in"]
            
            return HHUserAuth(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data["expires_in"],
                token_type=token_data.get("token_type", "bearer"),
                expires_at=expires_at
            )
    
    async def revoke_token(self, access_token: str) -> bool:
        """Инвалидация access токена"""
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": settings.hh_user_agent
            }
            
            response = await client.delete(f"{self.api_url}/token", headers=headers)
            
            return response.status_code == 204


# Глобальный экземпляр OAuth клиента
hh_oauth_client = HHOAuthClient() 