import hashlib
from datetime import UTC, date, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.outbound.persistence.models.raw_snapshot import RawSnapshotModel

_SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "proxy-authorization"}


class SqlAlchemyRawSnapshotRepository:
    def __init__(self, sessions: async_sessionmaker, max_bytes: int) -> None:
        self.sessions = sessions
        self.max_bytes = max_bytes

    async def save_http(
        self,
        target_date: date,
        request_url: str,
        response_status: int,
        headers: dict[str, str],
        body: str,
    ) -> int:
        truncated = body.encode("utf-8")[: self.max_bytes].decode("utf-8", errors="ignore")
        safe_headers = {
            key: value for key, value in headers.items() if key.lower() not in _SENSITIVE_HEADERS
        }
        model = RawSnapshotModel(
            source="kbo-http",
            target_date=target_date,
            request_url=request_url,
            request_method="POST",
            request_params=None,
            response_status=response_status,
            response_headers=safe_headers,
            response_body=truncated,
            body_hash=hashlib.sha256(truncated.encode()).hexdigest(),
            collected_at=datetime.now(UTC),
            parser_version="kbo-schedule-json-v1",
            parse_status="pending",
            parse_error=None,
        )
        async with self.sessions() as session, session.begin():
            session.add(model)
            await session.flush()
            return model.id

    async def mark(self, snapshot_id: int, succeeded: bool, error: str | None = None) -> None:
        async with self.sessions() as session, session.begin():
            await session.execute(
                update(RawSnapshotModel)
                .where(RawSnapshotModel.id == snapshot_id)
                .values(parse_status="succeeded" if succeeded else "failed", parse_error=error)
            )
