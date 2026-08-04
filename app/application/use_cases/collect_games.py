import hashlib
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.outbound.persistence.models.collection_job import CollectionJobModel
from app.adapters.outbound.persistence.models.game import GameModel
from app.adapters.outbound.persistence.models.game_revision import GameRevisionModel
from app.adapters.outbound.persistence.models.team import TeamModel
from app.application.dto.collection_result import CollectionResult
from app.application.ports.outbound.game_source import GameSource
from app.domain.enums.collection_status import CollectionStatus
from app.domain.exceptions import CollectionInProgressError
from app.domain.services.game_change_detector import (
    canonical_hash,
    canonical_payload,
    changed_fields,
)


class CollectGamesUseCase:
    """Coordinates collection and persists game/revision changes atomically."""

    def __init__(self, source: GameSource, sessions: async_sessionmaker) -> None:
        self.source, self.sessions = source, sessions

    async def execute(self, target_date: date) -> CollectionResult:
        games = await self.source.fetch_games(target_date)
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            # transaction-scoped advisory lock; released automatically on commit/rollback
            digest = hashlib.blake2b(
                f"kbo:collection:{target_date.isoformat()}".encode(), digest_size=8
            ).digest()
            lock_key = int.from_bytes(digest, byteorder="big", signed=True)
            lock = await session.scalar(
                select(__import__("sqlalchemy").func.pg_try_advisory_xact_lock(lock_key))
            )
            if not lock:
                raise CollectionInProgressError()
            job = CollectionJobModel(
                job_type="collect_date",
                target_date=target_date,
                source="kbo",
                status=CollectionStatus.RUNNING.value,
                started_at=now,
                attempt_count=1,
                fetched_count=len(games),
                inserted_count=0,
                updated_count=0,
                unchanged_count=0,
                failed_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add(job)
            teams = {team.code: team for team in (await session.scalars(select(TeamModel))).all()}
            for source_game in games:
                try:
                    away, home = (
                        teams[source_game.away_team_code],
                        teams[source_game.home_team_code],
                    )
                    existing = await self._find_existing(session, source_game, away.id, home.id)
                    new_hash = canonical_hash(source_game)
                    if existing is None:
                        game = self._model(source_game, away.id, home.id, new_hash, now)
                        session.add(game)
                        await session.flush()
                        session.add(self._revision(game, source_game, now, {}))
                        job.inserted_count += 1
                    elif existing.canonical_hash == new_hash:
                        existing.last_collected_at = now
                        existing.updated_at = now
                        job.unchanged_count += 1
                    else:
                        before = self._source_view(existing)
                        changes = changed_fields(before, source_game)
                        self._update(existing, source_game, new_hash, now)
                        existing.revision += 1
                        session.add(self._revision(existing, source_game, now, changes))
                        job.updated_count += 1
                except Exception:
                    job.failed_count += 1
            job.status = (
                CollectionStatus.PARTIALLY_SUCCEEDED.value
                if job.failed_count
                else CollectionStatus.SUCCEEDED.value
            )
            job.finished_at = datetime.now(UTC)
            job.updated_at = job.finished_at
            await session.flush()
            return CollectionResult(
                job.id,
                CollectionStatus(job.status),
                job.fetched_count,
                job.inserted_count,
                job.updated_count,
                job.unchanged_count,
                job.failed_count,
            )

    async def _find_existing(self, session, source_game, away_id: int, home_id: int):
        if source_game.source_game_id:
            found = await session.scalar(
                select(GameModel).where(GameModel.source_game_id == source_game.source_game_id)
            )
            if found:
                return found
        return await session.scalar(
            select(GameModel).where(
                GameModel.season == source_game.season,
                GameModel.league_type == source_game.league_type.value,
                GameModel.game_date == source_game.game_date,
                GameModel.away_team_id == away_id,
                GameModel.home_team_id == home_id,
                GameModel.scheduled_at == source_game.scheduled_at,
            )
        )

    def _model(self, dto, away_id, home_id, digest, now):
        model = GameModel(
            source=dto.source,
            source_game_id=dto.source_game_id,
            season=dto.season,
            league_type=dto.league_type.value,
            game_date=dto.game_date,
            scheduled_at=dto.scheduled_at,
            stadium=dto.stadium,
            status=dto.status.value,
            source_status_text=dto.source_status_text,
            away_team_id=away_id,
            home_team_id=home_id,
            away_score=dto.away_score,
            home_score=dto.home_score,
            inning=dto.inning,
            result_text=dto.result_text,
            winning_pitcher=dto.winning_pitcher,
            losing_pitcher=dto.losing_pitcher,
            save_pitcher=dto.save_pitcher,
            attendance=dto.attendance,
            source_url=dto.source_url,
            source_updated_at=dto.source_updated_at,
            first_collected_at=now,
            last_collected_at=now,
            revision=1,
            canonical_hash=digest,
            created_at=now,
            updated_at=now,
        )
        return model

    def _update(self, game, dto, digest, now):
        for name in (
            "source_game_id",
            "scheduled_at",
            "stadium",
            "away_score",
            "home_score",
            "inning",
            "result_text",
            "winning_pitcher",
            "losing_pitcher",
            "save_pitcher",
            "attendance",
            "source_url",
            "source_updated_at",
            "source_status_text",
        ):
            setattr(game, name, getattr(dto, name))
        game.status, game.canonical_hash, game.last_collected_at, game.updated_at = (
            dto.status.value,
            digest,
            now,
            now,
        )

    def _source_view(self, game):
        return {
            key: getattr(game, key)
            for key in (
                "status",
                "source_status_text",
                "scheduled_at",
                "stadium",
                "away_score",
                "home_score",
                "inning",
                "result_text",
                "winning_pitcher",
                "losing_pitcher",
                "save_pitcher",
                "attendance",
            )
        }

    def _revision(self, game, dto, now, changes):
        return GameRevisionModel(
            game_id=game.id,
            revision=game.revision,
            status=dto.status.value,
            away_score=dto.away_score,
            home_score=dto.home_score,
            data=canonical_payload(dto),
            changed_fields=changes,
            collected_at=now,
        )
