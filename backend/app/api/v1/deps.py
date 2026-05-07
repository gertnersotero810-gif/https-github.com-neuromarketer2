import uuid
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
import jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core import security

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

async def get_db_shared() -> AsyncGenerator[AsyncSession, None]:
    """Database session without RLS context (for auth, registration, etc)"""
    async with AsyncSessionLocal() as session:
        yield session

async def get_db(
    token: str = Depends(reusable_oauth2)
) -> AsyncGenerator[AsyncSession, None]:
    """Database session with RLS context applied."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant context missing in token",
            )
        # Strictly validate UUID
        tenant_uuid = uuid.UUID(tenant_id)
    except (jwt.PyJWTError, ValidationError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or tenant context",
        )

    async with AsyncSessionLocal() as session:
        # Set tenant context for RLS
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_uuid)}
        )
        yield session

async def get_current_user(
    db: AsyncSession = Depends(get_db_shared),
    token: str = Depends(reusable_oauth2)
) -> User:
    """Validate JWT and return the current user."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_type = payload.get("type")
        if token_type != "access":
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
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject",
            )
    except (jwt.PyJWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    # Check user in DB
    result = await db.execute(text("SELECT * FROM users WHERE id = :uid AND is_active = true"), {"uid": user_uuid})
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create a user object to return
    # Since we are not using full ORM object fetching here, we can construct the SQLAlchemy model instance or dict.
    # To be safe and compliant with SQLModel/SQLAlchemy 2.0, let's fetch via ORM
    from sqlalchemy.future import select
    orm_result = await db.execute(select(User).where(User.id == user_uuid, User.is_active == True))
    orm_user = orm_result.scalars().first()
    
    if not orm_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return orm_user

async def get_llm_provider(
    db: AsyncSession = Depends(get_db)
) -> "LLMProvider":
    from app.core.llm_providers.openai_provider import OpenAIProvider
    
    # In a real app we'd load API key and base url from settings
    # Here we can just hardcode for testing if they are missing
    api_key = getattr(settings, "OPENAI_API_KEY", "test-key")
    base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
    
    return OpenAIProvider(
        api_key=api_key,
        model=model,
        base_url=base_url,
        db=db
    )
