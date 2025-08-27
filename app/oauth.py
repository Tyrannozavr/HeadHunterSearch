from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, OAuthState, HHUserCredentials, User
from app.utils.auth import get_current_user
from app.utils.hh_oauth import HHOAuthClient
from app.config import settings
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets

router = APIRouter(prefix="/oauth", tags=["oauth"])

# Создаем OAuth клиент
oauth_client = HHOAuthClient()

@router.get("/authorize")
async def authorize(
    request: Request,
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Начало OAuth авторизации"""
    try:
        # Генерируем уникальный state для безопасности
        state = secrets.token_urlsafe(32)
        
        # Сохраняем state в базе
        oauth_state = OAuthState(
            state=state,
            user_id=current_user_id
        )
        session.add(oauth_state)
        await session.commit()
        
        # Формируем URL для авторизации
        auth_url = oauth_client.generate_authorization_url(current_user_id, state)
        
        # Возвращаем JSON с URL вместо прямого перенаправления
        return {
            "authorization_url": auth_url,
            "state": state,
            "message": "URL для авторизации сгенерирован"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка авторизации: {str(e)}")

@router.get("/callback")
async def callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_db)
):
    """OAuth callback - обмен кода на токены"""
    try:
        # Проверяем state
        result = await session.execute(
            select(OAuthState).where(
                OAuthState.state == state,
                OAuthState.created_at >= datetime.now() - timedelta(minutes=10)
            )
        )
        oauth_state = result.scalar_one_or_none()
        
        if not oauth_state:
            raise HTTPException(status_code=400, detail="Неверный или устаревший state")
        
        user_id = oauth_state.user_id
        
        # Обмениваем код на токены
        user_auth = await oauth_client.exchange_code_for_tokens(code)
        
        # Сохраняем токены в базе
        credentials = HHUserCredentials(
            user_id=user_id,
            access_token=user_auth.access_token,
            refresh_token=user_auth.refresh_token,
            expires_at=datetime.fromtimestamp(user_auth.expires_at) if user_auth.expires_at else None
        )
        
        session.add(credentials)
        
        # Удаляем использованный state
        await session.delete(oauth_state)
        
        await session.commit()
        
        # Перенаправляем на главную страницу
        return RedirectResponse(url="/?oauth_success=true")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка callback: {str(e)}")

@router.post("/refresh")
async def refresh_token(
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Обновление access token"""
    try:
        # Получаем текущие credentials пользователя
        result = await session.execute(
            select(HHUserCredentials).where(
                HHUserCredentials.user_id == current_user_id
            ).order_by(HHUserCredentials.created_at.desc()).limit(1)
        )
        credentials = result.scalar_one_or_none()
        
        if not credentials or not credentials.refresh_token:
            raise HTTPException(status_code=400, detail="Нет refresh token для обновления")
        
        # Обновляем токен
        new_auth = await oauth_client.refresh_tokens(credentials.refresh_token)
        
        # Обновляем credentials в базе
        credentials.access_token = new_auth.access_token
        if new_auth.refresh_token:
            credentials.refresh_token = new_auth.refresh_token
        credentials.expires_at = datetime.fromtimestamp(new_auth.expires_at) if new_auth.expires_at else None
        
        await session.commit()
        
        return {"message": "Токен успешно обновлен"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления токена: {str(e)}")

@router.post("/revoke")
async def revoke_token(
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Отзыв токенов пользователя"""
    try:
        # Получаем credentials пользователя
        result = await session.execute(
            select(HHUserCredentials).where(
                HHUserCredentials.user_id == current_user_id
            )
        )
        credentials_list = result.scalars().all()
        
        if not credentials_list:
            raise HTTPException(status_code=400, detail="Нет активных токенов")
        
        # Отзываем токены через API HH.ru
        for credentials in credentials_list:
            if credentials.access_token:
                try:
                    await oauth_client.revoke_token(credentials.access_token)
                except:
                    pass  # Игнорируем ошибки отзыва
        
        # Удаляем credentials из базы
        for credentials in credentials_list:
            await session.delete(credentials)
        
        await session.commit()
        
        return {"message": "Токены успешно отозваны"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отзыва токенов: {str(e)}")

@router.get("/status")
async def get_oauth_status(
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Получение статуса OAuth подключения"""
    try:
        # Получаем последние credentials пользователя
        result = await session.execute(
            select(HHUserCredentials).where(
                HHUserCredentials.user_id == current_user_id
            ).order_by(HHUserCredentials.created_at.desc()).limit(1)
        )
        credentials = result.scalar_one_or_none()
        
        if not credentials:
            return {
                "connected": False,
                "message": "Не подключен к HH.ru"
            }
        
        # Проверяем, не истек ли токен
        if credentials.expires_at and credentials.expires_at <= datetime.now():
            return {
                "connected": False,
                "message": "Токен истек, требуется обновление"
            }
        
        return {
            "connected": True,
            "message": "Подключен к HH.ru",
            "expires_at": credentials.expires_at.isoformat() if credentials.expires_at else None,
            "has_resume": bool(credentials.resume_id)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}") 