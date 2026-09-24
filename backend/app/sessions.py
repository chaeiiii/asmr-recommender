"""Signed anonymous identity and persisted onboarding resume state."""

import hashlib
import hmac
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import User, UserLanguagePreference
from app.taxonomy import TAXONOMY_VERSION

router = APIRouter()
COOKIE_NAME = "asmr_session"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60


def session_settings() -> tuple[bytes, bool]:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    secret = os.getenv("SESSION_SECRET", "")
    if len(secret.encode()) < 32:
        raise ValueError("Set SESSION_SECRET to a random secret of at least 32 bytes")
    secure = os.getenv("SESSION_COOKIE_SECURE", "true").lower()
    if secure not in {"true", "false"}:
        raise ValueError("SESSION_COOKIE_SECURE must be true or false")
    return secret.encode(), secure == "true"


def sign_identity(user_id: UUID, secret: bytes) -> str:
    identity = str(user_id)
    signature = hmac.new(secret, identity.encode(), hashlib.sha256).hexdigest()
    return f"{identity}.{signature}"


def read_identity(cookie: str | None, secret: bytes) -> UUID | None:
    if not cookie or len(cookie) != 101:
        return None
    identity, _, signature = cookie.partition(".")
    expected = hmac.new(secret, identity.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        return None
    try:
        return UUID(identity)
    except ValueError:
        return None


def get_anonymous_user(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_session)],
) -> User:
    secret, secure = session_settings()
    identity = read_identity(request.cookies.get(COOKIE_NAME), secret)
    user = db.get(User, identity) if identity is not None else None
    if user is None:
        user = User(
            created_at=datetime.now(timezone.utc),
            taxonomy_version=TAXONOMY_VERSION,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    response.set_cookie(
        COOKIE_NAME,
        sign_identity(user.id, secret),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return user


def next_route(user: User, db: Session) -> str:
    if user.onboarding_completed:
        return "/home"
    if user.initial_test_completed_at is None:
        return "/test"
    if user.voice_mode is None:
        return "/onboarding/voice"
    if user.voice_mode != "no_talking" and not user.language_no_preference:
        language = db.scalar(
            select(UserLanguagePreference.language)
            .where(UserLanguagePreference.user_id == user.id)
            .limit(1)
        )
        if language is None:
            return "/onboarding/languages"
    return "/onboarding/extra-preferences"


class SessionState(BaseModel):
    initial_test_completed: bool
    onboarding_completed: bool
    next_route: str


@router.post("/session", response_model=SessionState)
def create_or_resume_session(
    user: Annotated[User, Depends(get_anonymous_user)],
    db: Annotated[Session, Depends(get_session)],
) -> SessionState:
    return SessionState(
        initial_test_completed=user.initial_test_completed_at is not None,
        onboarding_completed=user.onboarding_completed,
        next_route=next_route(user, db),
    )
