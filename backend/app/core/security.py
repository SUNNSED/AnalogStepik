import hashlib
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt
from app.core.config import settings

# Вспомогательная функция для подготовки пароля (SHA-256)
def _prepare_password(password: str) -> bytes:
    # Хешируем пароль в SHA-256, чтобы обойти лимит bcrypt в 72 байта.
    # Результат всегда 64 символа (64 байта в UTF-8).
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # Пытаемся проверить с SHA-256 (новый формат)
        prepared_password = _prepare_password(plain_password)
        if bcrypt.checkpw(prepared_password, hashed_password.encode("utf-8")):
            return True
    except Exception:
        pass

    try:
        # Резервный вариант для старых паролей (без SHA-256)
        # Если пароль > 72 байт, bcrypt сам выбросит ошибку, что корректно для старых записей
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    # Готовим пароль (SHA-256)
    prepared_password = _prepare_password(password)
    # Генерируем соль и хеш
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(prepared_password, salt)
    return hashed.decode("utf-8")

def create_access_token(subject: Any, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

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
