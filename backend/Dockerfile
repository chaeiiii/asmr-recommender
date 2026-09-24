FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations
RUN pip install --no-cache-dir . && useradd --create-home app
USER app
EXPOSE 8000
CMD ["sh", "-c", "python -c 'from app.sessions import session_settings; session_settings()' && python -m alembic upgrade head && python -m app.seed_taxonomy && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
