import asyncio
import sys
from datetime import date

import uvicorn


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "api"
    if command == "api":
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
    elif command == "migrate":
        from alembic.config import main as alembic_main
        alembic_main(argv=["upgrade", "head"])
    elif command in {"worker", "collect-date", "backfill"}:
        # Worker scheduling belongs here; the command boundary is intentionally separate from API.
        if command == "collect-date" and len(sys.argv) > 2:
            date.fromisoformat(sys.argv[2])
        raise SystemExit("Collection worker wiring requires a verified KBO endpoint/parser configuration.")
    else:
        raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__": main()
