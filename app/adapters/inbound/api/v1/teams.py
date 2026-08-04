from fastapi import APIRouter, Request
from sqlalchemy import select
from app.adapters.outbound.persistence.models.team import TeamModel

router = APIRouter(prefix="/api/v1", tags=["teams"])

@router.get("/teams")
async def teams(request: Request) -> dict:
    async with request.app.state.session_factory() as session: rows = (await session.scalars(select(TeamModel).order_by(TeamModel.code))).all()
    return {"teams": [{"code": row.code, "name": row.name, "shortName": row.short_name, "active": row.active} for row in rows]}
