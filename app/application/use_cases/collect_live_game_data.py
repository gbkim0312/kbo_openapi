from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.outbound.persistence.models.at_bat_event import AtBatEventModel
from app.adapters.outbound.persistence.models.game import GameModel
from app.adapters.outbound.persistence.models.preview import GameLineupSnapshotModel
from app.application.use_cases.collect_preview import CollectPreviewUseCase
from app.application.use_cases.collect_records import CollectRecordsUseCase


class CollectLiveGameDataUseCase:
    """Refreshes game-center data that can change near or during a game."""

    def __init__(
        self,
        records: CollectRecordsUseCase,
        previews: CollectPreviewUseCase,
        sessions: async_sessionmaker,
    ) -> None:
        self.records, self.previews, self.sessions = records, previews, sessions

    async def collect_previews(self, target_date: date) -> dict[str, int]:
        async with self.sessions() as session:
            game_ids = list(
                await session.scalars(
                    select(GameModel.id).where(
                        GameModel.game_date == target_date,
                        GameModel.status.in_(("scheduled", "pre_game", "in_progress")),
                    )
                )
            )
            confirmed_ids = set(
                await session.scalars(
                    select(GameLineupSnapshotModel.game_id).where(
                        GameLineupSnapshotModel.game_id.in_(game_ids),
                        GameLineupSnapshotModel.confirmed.is_(True),
                    )
                )
            )
        collected = failed = 0
        for game_id in game_ids:
            if game_id in confirmed_ids:
                continue
            try:
                await self.previews.execute(game_id)
                collected += 1
            except Exception:
                failed += 1
        return {
            "requested": len(game_ids) - len(confirmed_ids),
            "collected": collected,
            "failed": failed,
        }

    async def collect_live_details(self, target_date: date) -> dict[str, int]:
        now = datetime.now(UTC)
        async with self.sessions() as session:
            game_rows = (
                await session.execute(
                    select(GameModel.id, GameModel.status).where(
                        GameModel.game_date == target_date,
                        GameModel.status.in_(
                            (
                                "scheduled",
                                "pre_game",
                                "in_progress",
                                "delayed",
                                "suspended",
                                "completed",
                            )
                        ),
                        GameModel.scheduled_at.is_not(None),
                        GameModel.scheduled_at <= now,
                    )
                )
            ).all()
        collected = failed = 0
        for game_id, status in game_rows:
            scoreboard_ok = False
            try:
                scoreboard_ok = await self._collect_scoreboard(game_id)
            except Exception:
                pass
            if status == "completed":
                collected += 1 if scoreboard_ok else 0
                continue
            try:
                await self.records.collect_game_details(game_id)
                collected += 1 if scoreboard_ok else 0
            except Exception:
                if not scoreboard_ok:
                    failed += 1
        return {"requested": len(game_rows), "collected": collected, "failed": failed}

    async def _collect_scoreboard(self, game_id: int) -> bool:
        async with self.sessions() as session:
            game = await session.get(GameModel, game_id)
            if game is None or not game.source_game_id:
                return False
            scoreboard = await self.records.source.fetch_scoreboard(
                game.source_game_id, game.season
            )
            fetch_live_state = getattr(self.records.source, "fetch_live_state", None)
            live_state = (
                await fetch_live_state(game.source_game_id, game.season)
                if fetch_live_state
                else None
            )
        if scoreboard is None and live_state is None:
            return False
        collected_at = datetime.now(UTC)
        collected_at_text = collected_at.isoformat()
        if scoreboard is None:
            scoreboard = dict(game.scoreboard or {})
            scoreboard.setdefault("source", "naver-sports")
        else:
            scoreboard = dict(scoreboard)
            if game.scoreboard and "completedAtBat" in game.scoreboard:
                scoreboard.setdefault("completedAtBat", game.scoreboard["completedAtBat"])
            scoreboard["scoreUpdatedAt"] = collected_at_text
        if live_state is not None:
            live_state = {**live_state, "updatedAt": collected_at_text, "stale": False}
            if game.inning and not self._same_inning(game.inning, live_state):
                live_state.update(
                    {
                        "inning": self._inning_from_display(game.inning),
                        "pitcher": None,
                        "batter": None,
                        "count": None,
                        "runners": {"first": None, "second": None, "third": None},
                        "stale": True,
                    }
                )
            scoreboard["liveState"] = live_state
            scoreboard["liveFetchedAt"] = collected_at_text
            completed = live_state.get("completedAtBats")
            if isinstance(completed, list):
                if completed:
                    scoreboard["completedAtBat"] = completed[-1]
        elif not self._same_inning(game.inning, (game.scoreboard or {}).get("liveState")):
            # A new half-inning without a fresh relay must not expose the prior
            # half's batter, runners, or count.
            scoreboard["liveState"] = None
        elif scoreboard.get("liveState"):
            scoreboard["liveState"] = {
                **scoreboard["liveState"],
                "stale": True,
            }
        async with self.sessions() as session, session.begin():
            game = await session.get(GameModel, game_id)
            if game is not None:
                game.scoreboard = scoreboard
                game.updated_at = datetime.now(UTC)
                events = live_state.get("completedAtBats", []) if live_state else []
                if isinstance(events, list):
                    for event in events:
                        if not isinstance(event, dict):
                            continue
                        source_no = event.get("sourceEventNo")
                        source_seq = event.get("sourceSeqno")
                        if not isinstance(source_no, int) or not isinstance(source_seq, int):
                            continue
                        exists = await session.scalar(
                            select(AtBatEventModel.id).where(
                                AtBatEventModel.game_id == game_id,
                                AtBatEventModel.source_event_no == source_no,
                                AtBatEventModel.source_seqno == source_seq,
                            )
                        )
                        if exists:
                            continue
                        batter = (
                            event.get("batter") if isinstance(event.get("batter"), dict) else {}
                        )
                        session.add(
                            AtBatEventModel(
                                game_id=game_id,
                                source_event_no=source_no,
                                source_seqno=source_seq,
                                inning=event.get("inning"),
                                half=event.get("half"),
                                batter_id=batter.get("id"),
                                batter_name=batter.get("name"),
                                team_code=batter.get("team"),
                                result=event.get("result") or "other",
                                result_text=event.get("resultText") or "",
                                raw_text=event.get("rawText") or "",
                                runs=event.get("runs"),
                                rbi=event.get("rbi"),
                                occurred_at=None,
                                collected_at=collected_at,
                                raw=event,
                            )
                        )
                return True
        return False

    @staticmethod
    def _same_inning(game_inning: str | None, live_state: object) -> bool:
        if not game_inning or not isinstance(live_state, dict):
            return True
        inning = live_state.get("inning")
        if isinstance(inning, dict):
            return inning.get("display") == game_inning
        return inning == game_inning

    @staticmethod
    def _inning_from_display(display: str) -> dict[str, int | str] | None:
        if len(display) < 3 or not display.endswith(("회초", "회말")):
            return None
        number = display[:-2]
        if not number.isdigit():
            return None
        half = "bottom" if display.endswith("회말") else "top"
        return {"number": int(number), "half": half, "display": display}
