from enum import StrEnum


class LeagueType(StrEnum):
    REGULAR = "regular"
    POSTSEASON = "postseason"
    EXHIBITION = "exhibition"
    ALL_STAR = "all_star"
    UNKNOWN = "unknown"
