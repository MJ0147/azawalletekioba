from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool

from config import settings
from user import User

# Only relational (PostgreSQL / MySQL) back-ends benefit from connection pooling.
# Redis / SQLite or anything non-relational should use NullPool so SQLAlchemy
# does not try to manage persistent connections.
_RELATIONAL_SCHEMES = ("postgresql", "postgres", "mysql", "mssql", "oracle")
_is_relational = any(settings.DATABASE_URL.lower().startswith(s) for s in _RELATIONAL_SCHEMES)

_pool_kwargs = (
    {
        "pool_size": int(__import__("os").environ.get("DB_POOL_SIZE", "5")),
        "max_overflow": int(__import__("os").environ.get("DB_MAX_OVERFLOW", "10")),
        "pool_timeout": int(__import__("os").environ.get("DB_POOL_TIMEOUT", "30")),
        "pool_recycle": int(__import__("os").environ.get("DB_POOL_RECYCLE", "1800")),
    }
    if _is_relational
    else {"poolclass": NullPool}
)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # verify connection liveness before use
    **_pool_kwargs,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)

async def get_current_user(
    db: Session = Depends(get_db), 
    token: str = Depends(oauth2_scheme)
) -> User:
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
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
    
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user identifier in token",
        )
        
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user