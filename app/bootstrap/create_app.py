from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from app.adapters.inbound.api.exception_handlers import domain_error_handler, validation_error_handler
from app.adapters.inbound.api.v1.games import router as games_router
from app.adapters.inbound.api.v1.teams import router as teams_router
from app.domain.exceptions import DomainError
from app.infrastructure.config import settings
from app.adapters.outbound.persistence.database import make_session_factory


def create_app() -> FastAPI:
    app = FastAPI(title="KBO 경기 결과 API", version="0.1.0")
    app.state.session_factory = make_session_factory(settings.database_url)
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request); response.headers["X-Request-ID"] = request.state.request_id
        return response
    @app.get("/health/live")
    async def live() -> dict[str, str]: return {"status": "ok"}
    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        async with app.state.session_factory() as session: await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    app.include_router(games_router); app.include_router(teams_router)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    return app
