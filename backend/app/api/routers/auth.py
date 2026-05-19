from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError
from pydantic import ValidationError

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User
from app.core import security
from app.schemas.user import UserCreate, UserResponse, Token, RefreshToken

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):

    #Проверяем, существует ли уже пользователь с таким email
    query = select(User).where(User.email == user_in.email)
    result = await db.execute(query)
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    #Хэшируем пароль и создаем объект пользователя
    hashed_pwd = security.get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_pwd
    )

    #Сохраняем в базу данных
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user

@router.post("/login", response_model=Token)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db)
):
    #Ищем пользователя в базе, почта == username, тк так требуется
    query = select(User).where(User.email == form_data.username)
    result = await db.execute(query)
    user = result.scalars().first()

    #Проверяем существование пользователя и правильность пароля
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    #Генерируем токен, помещая туда ID пользователя
    access_token = security.create_access_token(subject=user.id)
    refresh_token = security.create_refresh_token(subject=user.id)

    # Возвращаем в формате, который ожидает протокол OAuth2
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: RefreshToken,
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = jwt.decode(
            token_data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    # Убедимся что юзер существует
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    access_token = security.create_access_token(subject=user.id)
    new_refresh_token = security.create_refresh_token(subject=user.id)

    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}