from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx

from app.infrastructure.config import Settings


class NaverSportsSource:
    """Adapter for Naver Sports' live baseball game-center payloads.

    The sports gateway is not a documented Naver Open API. Keep this adapter
    isolated so it can be disabled or replaced without changing the domain.
    """

    def __init__(self, config: Settings) -> None:
        self.config = config

    async def fetch_scoreboard(self, source_game_id: str, season: int) -> dict | None:
        naver_game_id = self.to_naver_game_id(source_game_id, season)
        url = f"{self.config.naver_sports_base_url}/schedule/games/{naver_game_id}/game-polling"
        async with httpx.AsyncClient(
            headers={"User-Agent": self.config.naver_sports_user_agent},
            timeout=self.config.naver_sports_timeout_seconds,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        payload = response.json()
        game = (payload.get("result") or {}).get("game") or {}
        if not isinstance(game, dict) or not game:
            return None
        return self._parse_scoreboard(game)

    async def fetch_live_state(self, source_game_id: str, season: int) -> dict | None:
        naver_game_id = self.to_naver_game_id(source_game_id, season)
        url = f"{self.config.naver_sports_base_url}/schedule/games/{naver_game_id}/relay"
        async with httpx.AsyncClient(
            headers={"User-Agent": self.config.naver_sports_user_agent},
            timeout=self.config.naver_sports_timeout_seconds,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        payload = response.json()
        relay = (payload.get("result") or {}).get("textRelayData") or {}
        if not isinstance(relay, dict):
            return None
        return self._parse_live_state(relay, source_game_id)

    @staticmethod
    def to_naver_game_id(source_game_id: str, season: int) -> str:
        """Map KBO's 20260919SSLT0 identity to Naver's 20260919SSLT02026."""
        return f"{source_game_id}{season}"

    @staticmethod
    def _parse_scoreboard(game: dict) -> dict | None:
        away_scores = NaverSportsSource._inning_values(game.get("awayTeamScoreByInning"))
        home_scores = NaverSportsSource._inning_values(game.get("homeTeamScoreByInning"))
        away_rheb = NaverSportsSource._rheb(game.get("awayTeamRheb"))
        home_rheb = NaverSportsSource._rheb(game.get("homeTeamRheb"))
        if not away_scores and not home_scores and away_rheb is None and home_rheb is None:
            return None

        innings = []
        for index in range(max(len(away_scores), len(home_scores))):
            away = away_scores[index] if index < len(away_scores) else None
            home = home_scores[index] if index < len(home_scores) else None
            if away is None and home is None:
                continue
            innings.append({"inning": index + 1, "away": away, "home": home})

        return {
            "innings": innings,
            "totals": {"away": away_rheb or {}, "home": home_rheb or {}},
            "maxInning": len(innings),
            "currentInning": game.get("currentInning"),
            "source": "naver-sports",
            "sourceGameId": game.get("gameId"),
            "fetchedAt": datetime.now(UTC).isoformat(),
            "startingPitchers": {
                "away": game.get("awayStarterName"),
                "home": game.get("homeStarterName"),
            },
        }

    @staticmethod
    def _parse_live_state(relay: dict, source_game_id: str) -> dict | None:
        state = relay.get("currentGameState")
        if not isinstance(state, dict):
            return None

        players: dict[str, dict[str, object]] = {}
        batters_by_order: dict[str, dict[str, dict[str, object]]] = {
            "home": {},
            "away": {},
        }
        for side, team_code, key in (
            ("home", source_game_id[10:12], "homeLineup"),
            ("away", source_game_id[8:10], "awayLineup"),
        ):
            lineup = relay.get(key)
            if not isinstance(lineup, dict):
                continue
            for group in ("batter", "pitcher"):
                for player in lineup.get(group, []):
                    if not isinstance(player, dict) or not player.get("pcode"):
                        continue
                    players[str(player["pcode"])] = {
                        "id": str(player["pcode"]),
                        "name": str(player.get("name")) if player.get("name") else None,
                        "team": team_code or None,
                        "side": side,
                    }
                    if group == "pitcher":
                        players[str(player["pcode"])] |= {
                            "pitchCount": NaverSportsSource._as_int(player.get("ballCount")),
                            "innings": player.get("inn"),
                            "hits": NaverSportsSource._as_int(player.get("hit")),
                            "runs": NaverSportsSource._as_int(player.get("run")),
                            "walks": NaverSportsSource._as_int(player.get("bb")),
                            "strikeouts": NaverSportsSource._as_int(player.get("kk")),
                        }
                    if group == "batter" and player.get("batOrder") is not None:
                        batters_by_order[side][str(player["batOrder"])] = players[
                            str(player["pcode"])
                        ]

        def player(
            value: object, side: str | None = None, runner: bool = False
        ) -> dict[str, object] | None:
            key = str(value or "")
            if not key or key == "0":
                return None
            if runner and side and key in batters_by_order[side]:
                return batters_by_order[side][key]
            return players.get(key, {"id": key, "name": None, "team": None, "side": None})

        def number(key: str) -> int | None:
            value = state.get(key)
            return int(str(value)) if str(value or "").isdigit() else None

        inning = NaverSportsSource._parse_inning(relay)
        offense_side = "home" if str(relay.get("homeOrAway") or "0") == "1" else "away"
        parsed = {
            "pitcher": player(state.get("pitcher")),
            "batter": player(state.get("batter")),
            "count": {
                "balls": number("ball"),
                "strikes": number("strike"),
                "outs": number("out"),
            },
            "runners": {
                "first": player(state.get("base1"), offense_side, runner=True),
                "second": player(state.get("base2"), offense_side, runner=True),
                "third": player(state.get("base3"), offense_side, runner=True),
            },
            "source": "naver-sports",
            "relayNumber": relay.get("no"),
            "playSequence": relay.get("no"),
            "inning": inning,
        }
        parsed["completedAtBats"] = NaverSportsSource._parse_completed_at_bats(
            relay, source_game_id
        )
        return parsed

    @staticmethod
    def _parse_completed_at_bats(relay: dict, source_game_id: str) -> list[dict[str, object]]:
        """Normalize result text from Naver's recent relay window.

        Naver does not publish a stable result enum or event timestamp.  We retain
        the raw Korean text and use ``no`` + ``seqno`` as the deduplication key.
        """
        result: list[dict[str, object]] = []
        relays = relay.get("textRelays")
        if not isinstance(relays, list):
            return result
        for relay_item in relays:
            if not isinstance(relay_item, dict):
                continue
            no = NaverSportsSource._as_int(relay_item.get("no"))
            inning = relay_item.get("inn")
            half = "bottom" if str(relay_item.get("homeOrAway") or "0") == "1" else "top"
            options = relay_item.get("textOptions")
            if not isinstance(options, list):
                continue
            for option in options:
                if not isinstance(option, dict) or option.get("type") != 13:
                    continue
                text = str(option.get("text") or "").strip()
                # Type 13 contains completed play text (and occasionally review
                # notices). Only expose a result when a batter/result separator is
                # present; raw text is still preserved for future parser updates.
                if ":" not in text:
                    continue
                seqno = NaverSportsSource._as_int(option.get("seqno"))
                if no is None or seqno is None:
                    continue
                record = option.get("batterRecord")
                record = record if isinstance(record, dict) else {}
                result.append(
                    {
                        "eventId": f"{source_game_id}-{no}-{seqno}",
                        "sourceEventNo": no,
                        "sourceSeqno": seqno,
                        "inning": int(inning) if str(inning).isdigit() else None,
                        "half": half,
                        "batter": {
                            "id": str(record["pcode"]) if record.get("pcode") else None,
                            "name": str(record["name"])
                            if record.get("name")
                            else text.split(":", 1)[0].strip(),
                            "team": source_game_id[8:10]
                            if half == "top"
                            else source_game_id[10:12],
                        },
                        "result": NaverSportsSource._result_code(text),
                        "resultText": text.split(":", 1)[1].strip(),
                        "rawText": text,
                        "runs": NaverSportsSource._as_int(record.get("run")),
                        "rbi": NaverSportsSource._as_int(record.get("rbi")),
                        "occurredAt": None,
                        "source": "naver-sports",
                    }
                )
        result.sort(key=lambda item: (item["sourceEventNo"], item["sourceSeqno"]))
        return result

    @staticmethod
    def _result_code(text: str) -> str:
        value = text.split(":", 1)[-1]
        patterns = (
            ("home_run", ("홈런",)),
            ("triple", ("3루타",)),
            ("double", ("2루타",)),
            ("single", ("안타", "1루타")),
            ("walk", ("볼넷", "4구")),
            ("hit_by_pitch", ("사구", "몸에 맞는 볼")),
            ("strikeout", ("삼진",)),
            ("double_play", ("병살",)),
            ("sacrifice", ("희생",)),
            ("error_reach", ("실책",)),
            ("groundout", ("땅볼 아웃", "땅볼아웃")),
            ("flyout", ("뜬공 아웃", "플라이 아웃", "직선타 아웃")),
        )
        for code, words in patterns:
            if any(word in value for word in words):
                return code
        return "other"

    @staticmethod
    def _parse_inning(relay: dict) -> dict[str, int | str] | None:
        # The relay title can lag behind currentGameState during a side change.
        # Prefer the machine-readable inning and attack-side fields first.
        number = relay.get("inn")
        side = relay.get("homeOrAway")
        if str(number).isdigit() and str(side) in {"0", "1"}:
            half = "bottom" if str(side) == "1" else "top"
            korean_half = "말" if half == "bottom" else "초"
            return {
                "number": int(str(number)),
                "half": half,
                "display": f"{number}회{korean_half}",
            }
        relays = relay.get("textRelays")
        if isinstance(relays, list):
            for item in reversed(relays):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "")
                match = re.search(r"(\d+)회\s*(초|말)", title)
                if match:
                    half = "top" if match.group(2) == "초" else "bottom"
                    return {
                        "number": int(match.group(1)),
                        "half": half,
                        "display": f"{match.group(1)}회{match.group(2)}",
                    }
        if str(number).isdigit():
            side = str(relay.get("homeOrAway") or "0")
            half = "bottom" if side == "1" else "top"
            korean_half = "말" if half == "bottom" else "초"
            return {
                "number": int(str(number)),
                "half": half,
                "display": f"{number}회{korean_half}",
            }
        return None

    @staticmethod
    def _inning_values(value: object) -> list[int | None]:
        if not isinstance(value, list):
            return []
        result: list[int | None] = []
        for item in value:
            text = str(item).strip()
            result.append(int(text) if text.isdigit() else None)
        return result

    @staticmethod
    def _as_int(value: object) -> int | None:
        if value is None:
            return None
        text = str(value).strip()
        return int(text) if text.isdigit() else None

    @staticmethod
    def _rheb(value: object) -> dict[str, int | None] | None:
        if not isinstance(value, list) or len(value) < 4:
            return None
        keys = ("runs", "hits", "errors", "walks")
        return {
            key: int(value[index]) if str(value[index]).strip().isdigit() else None
            for index, key in enumerate(keys)
        }
