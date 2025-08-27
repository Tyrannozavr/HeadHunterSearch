from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, User
from app.utils.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.types import UserCreate, UserLogin, UserResponse
from sqlalchemy import select

router = APIRouter(prefix="/api/auth", tags=["auth"])

security = HTTPBearer()

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_db)
):
    """Регистрация нового пользователя"""
    try:
        # Проверяем, не существует ли уже пользователь с таким username или email
        existing_user = await session.execute(
            select(User).where(
                (User.username == user_data.username) | (User.email == user_data.email)
            )
        )
        
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Пользователь с таким username или email уже существует"
            )
        
        # Создаем нового пользователя
        hashed_password = get_password_hash(user_data.password)
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            role=user_data.role,
            is_active=True
        )
        
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        
        return UserResponse.from_orm(new_user)
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка регистрации: {str(e)}")

@router.post("/login")
async def login(
    user_data: UserLogin,
    session: AsyncSession = Depends(get_db)
):
    """Вход пользователя"""
    try:
        # Ищем пользователя по username
        result = await session.execute(
            select(User).where(User.username == user_data.username)
        )
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(user_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный username или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь деактивирован"
            )
        
        # Создаем access token
        access_token = create_access_token(
            data={"sub": str(user.id), "username": user.username, "role": user.role}
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "username": user.username,
            "role": user.role
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка входа: {str(e)}")

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Получение информации о текущем пользователе"""
    try:
        result = await session.execute(
            select(User).where(User.id == current_user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Пользователь не найден"
            )
        
        return UserResponse.from_orm(user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения данных пользователя: {str(e)}") 