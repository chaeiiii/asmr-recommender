"""Minimal API bootstrap; persistence and product routes come in later tasks."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ASMR Recommender API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
    allow_methods=["GET"],
    allow_headers=[],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
