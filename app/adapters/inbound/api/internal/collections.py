from datetime import date

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.use_cases.collect_all import CollectAllUseCase
from app.application.use_cases.collect_games import CollectGamesUseCase
from app.application.use_cases.collect_records import CollectRecordsUseCase
from app.infrastructure.config import settings

router = APIRouter(prefix="/internal/v1", tags=["internal"])


class CollectionRequest(BaseModel):
    target_date: date = Field(alias="targetDate")
    force: bool = False


def authorize(authorization: str | None) -> None:
    if authorization != f"Bearer {settings.admin_api_key}":
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")


@router.post("/collections")
async def collect(
    payload: CollectionRequest, request: Request, authorization: str | None = Header(None)
) -> dict:
    authorize(authorization)
    result = await CollectGamesUseCase(
        request.app.state.game_source, request.app.state.session_factory
    ).execute(payload.target_date)
    return {
        "jobId": str(result.job_id),
        "status": result.status.value,
        "targetDate": payload.target_date,
        "fetchedCount": result.fetched_count,
        "insertedCount": result.inserted_count,
        "updatedCount": result.updated_count,
        "unchangedCount": result.unchanged_count,
        "failedCount": result.failed_count,
    }


@router.post("/collections/all")
async def collect_all(
    payload: CollectionRequest, request: Request, authorization: str | None = Header(None)
) -> dict:
    authorize(authorization)
    games = CollectGamesUseCase(request.app.state.game_source, request.app.state.session_factory)
    records = CollectRecordsUseCase(
        request.app.state.record_source, request.app.state.session_factory
    )
    return await CollectAllUseCase(games, records, request.app.state.session_factory).execute(
        payload.target_date
    )
