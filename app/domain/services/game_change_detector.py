import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any


CANONICAL_FIELDS = (
    "status", "source_status_text", "scheduled_at", "stadium", "away_score", "home_score",
    "inning", "result_text", "winning_pitcher", "losing_pitcher", "save_pitcher", "attendance",
)


def _value(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else getattr(value, "value", value)


def canonical_payload(game: Any) -> dict[str, Any]:
    values = asdict(game) if hasattr(game, "__dataclass_fields__") else game
    return {field: _value(values[field] if isinstance(values, dict) else getattr(values, field)) for field in CANONICAL_FIELDS}


def canonical_hash(game: Any) -> str:
    body = json.dumps(canonical_payload(game), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def changed_fields(before: Any, after: Any) -> dict[str, dict[str, Any]]:
    old, new = canonical_payload(before), canonical_payload(after)
    return {key: {"before": old[key], "after": new[key]} for key in CANONICAL_FIELDS if old[key] != new[key]}
