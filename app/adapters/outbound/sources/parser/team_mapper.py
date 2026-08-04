from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Team:
    code: str
    name: str
    short_name: str


TEAMS = (
    Team("LG", "LG 트윈스", "LG"),
    Team("HH", "한화 이글스", "한화"),
    Team("SK", "SSG 랜더스", "SSG"),
    Team("SS", "삼성 라이온즈", "삼성"),
    Team("NC", "NC 다이노스", "NC"),
    Team("KT", "KT 위즈", "KT"),
    Team("LT", "롯데 자이언츠", "롯데"),
    Team("HT", "KIA 타이거즈", "KIA"),
    Team("OB", "두산 베어스", "두산"),
    Team("WO", "키움 히어로즈", "키움"),
)
_BY_NAME = {
    alias: team for team in TEAMS for alias in (team.name, team.short_name, team.name.split()[0])
}


def normalize_team(name: str) -> Team:
    normalized = (
        name.strip().upper()
        if name.strip().upper() in {"LG", "NC", "KT", "SSG", "KIA"}
        else name.strip()
    )
    try:
        return _BY_NAME[normalized]
    except KeyError as error:
        raise ValueError(f"unknown KBO team: {name}") from error
