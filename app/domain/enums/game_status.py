from enum import StrEnum


class GameStatus(StrEnum):
    SCHEDULED = "scheduled"
    PRE_GAME = "pre_game"
    IN_PROGRESS = "in_progress"
    DELAYED = "delayed"
    SUSPENDED = "suspended"
    POSTPONED = "postponed"
    CANCELED = "canceled"
    COMPLETED = "completed"
    UNKNOWN = "unknown"
