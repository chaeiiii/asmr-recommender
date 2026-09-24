"""API entry point."""

import os
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.catalog import router as catalog_router
from app.onboarding import router as onboarding_router
from app.recommender import router as recommender_router
from app.sessions import router as session_router
from app.sound_test import router as sound_test_router


def cors_origins() -> list[str]:
    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "*" in origin
            or any(character.isspace() for character in origin)
        ):
            raise ValueError("CORS_ORIGINS must contain exact HTTP(S) origins")
        # Access validates malformed ports without echoing the configured value.
        try:
            parsed.port
        except ValueError:
            raise ValueError("CORS_ORIGINS contains an invalid port") from None
    return origins


app = FastAPI(title="ASMR Recommender API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(session_router, prefix="/api/v1")
app.include_router(sound_test_router, prefix="/api/v1")
app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(recommender_router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
