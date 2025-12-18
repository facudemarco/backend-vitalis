from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, status, HTTPException, Request
from jose import JWTError, jwt, ExpiredSignatureError
from datetime import datetime, timedelta
from typing import Optional, Callable
from sqlalchemy import text
from Database.getConnection import engine

from models.user import User

SECRET_KEY = "MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_Vitalis"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login",
    auto_error=False,
    scheme_name="OAuth2PasswordBearer",
    description="Autenticación mediante usuario y contraseña"
)

def create_access_token(data: dict):
    """Crea JWT con solo: id, role, exp"""
    to_encode = {
        "id": data.get("id"),
        "role": data.get("role")
    }
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """Verifica JWT y devuelve payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("id") is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(request: Request):
    token = request.cookies.get("Authorization")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not found in cookies",
        )

    if token.startswith("Bearer "):
        token = token[len("Bearer "):]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id = payload.get("id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT * FROM users WHERE id = :id"),
            {"id": user_id},
        ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return User(
        id=row["id"],
        email=row["email"],
        hashed_password=row["hashed_password"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        dni=row["dni"],
        date_of_birth=row["date_of_birth"],
        phone=row["phone"],
        role=row["role"],
        is_active=row["is_active"],
    )

def require_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Verifica que el usuario esté activo"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return current_user

def require_roles(*allowed_roles: str) -> Callable:
    """Decorador que requiere uno de los roles especificados"""
    async def check_role(current_user: User = Depends(require_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden. Required roles: {', '.join(allowed_roles)}",
            )
        return current_user
    return check_role