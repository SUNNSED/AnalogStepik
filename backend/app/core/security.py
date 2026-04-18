from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt
from passlib.context import CryptContext
from backend.app.core.config import settings

pwd_context = CryptContext(shemas=["bcrypt"], deprecated="auto")

#Для сравнения хэшированного пароля пользователя и пароля от пользователя в базе
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

#Непосредственно генерация хэша из пароля
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

#Создание JWT токена
def create_access_token(subject: Any, expires_delta: Optional[timedelta] = None) -> str: #Any, потому что пока не знаю что передавать, либо почту, либо id пользователя
    if expires_delta: #Задаток на будущее, вдруг понадобиться необычный токен (для восстановления пароля или что-то такое)
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES) #Обычное время жизни токена

    to_encode = {
        "exp": expire,
        "sub": str(subject)
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt