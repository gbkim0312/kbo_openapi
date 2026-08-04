FROM python:3.13-slim AS runtime
WORKDIR /app
RUN useradd --create-home appuser
COPY pyproject.toml ./
RUN pip install --no-cache-dir fastapi 'uvicorn[standard]' 'sqlalchemy[asyncio]' asyncpg 'psycopg[binary]' alembic httpx beautifulsoup4 pydantic-settings apscheduler
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
USER appuser
ENTRYPOINT ["python", "-m", "app.cli"]
