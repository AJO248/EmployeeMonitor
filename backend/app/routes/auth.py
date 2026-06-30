from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_session
from ..schemas import LoginRequest, TokenResponse
from ..security import authenticate_admin, create_access_token, require_admin, hash_password
from ..models import AdminUser
import sqlalchemy.exc

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    user = await authenticate_admin(request.username, request.password, session)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user.username)
    response.set_cookie(
        "em_access_token",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.access_token_minutes * 60,
    )
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie("em_access_token")


@router.post("/register")
async def register_admin(
    request: LoginRequest,
    current_user: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        new_admin = AdminUser(
            username=request.username,
            password_hash=hash_password(request.password)
        )
        session.add(new_admin)
        await session.commit()
        return {"detail": "Admin user created successfully"}
    except sqlalchemy.exc.IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Username already exists")
