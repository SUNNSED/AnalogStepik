from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core import security
from app.db.database import get_db
from app.db.models import User
from sqlalchemy.sql.functions import current_user

#Указываем, где искать токен
reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

#Проверяем токен и добываем текущего пользователя
async def get_current_user(
        db: AsyncSession = Depends(get_db),
        token: str = Depends(reusable_oauth2)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type", "access") != "access":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token type",
            )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
        )
    return user

async def get_current_teacher(current_user: User = Depends(get_current_user)):
    if not current_user.is_teacher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a teacher",
        )
    return current_user