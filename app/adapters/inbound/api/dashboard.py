from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(include_in_schema=False)
_DASHBOARD_PATH = Path(__file__).with_name("static") / "dashboard.html"


@router.get("/admin", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(_DASHBOARD_PATH, media_type="text/html")
