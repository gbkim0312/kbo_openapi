import logging

from app.domain.enums.game_status import GameStatus

_MAP = {
    "경기종료": GameStatus.COMPLETED,
    "종료": GameStatus.COMPLETED,
    "경기전": GameStatus.PRE_GAME,
    "예정": GameStatus.SCHEDULED,
    "경기중": GameStatus.IN_PROGRESS,
    "진행중": GameStatus.IN_PROGRESS,
    "우천취소": GameStatus.CANCELED,
    "취소": GameStatus.CANCELED,
    "연기": GameStatus.POSTPONED,
    "중단": GameStatus.SUSPENDED,
    "지연": GameStatus.DELAYED,
    "폭염취소": GameStatus.CANCELED,
    "미세먼지취소": GameStatus.CANCELED,
}


def map_status(value: str | None) -> GameStatus:
    if not value:
        return GameStatus.UNKNOWN
    result = _MAP.get(value.strip(), GameStatus.UNKNOWN)
    if result is GameStatus.UNKNOWN:
        logging.getLogger(__name__).warning(
            "unknown KBO status", extra={"source_status_text": value}
        )
    return result
