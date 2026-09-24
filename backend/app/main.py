"""API entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.catalog import router as catalog_router
from app.onboarding import router as onboarding_router
from app.recommender import router as recommender_router
from app.sessions import router as session_router
from app.sound_test import router as sound_test_router

app = FastAPI(title="ASMR Recommender API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
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
