# KBO 경기 결과 OpenAPI

KBO 경기 일정·결과를 수집해 PostgreSQL에 보존하고 REST/OpenAPI로 제공하기 위한 FastAPI 서비스입니다. 공개 조회 API는 KBO 사이트를 직접 호출하지 않으며, 수집 어댑터와 API 프로세스의 경계를 분리합니다.

## 현재 구현 범위

- Python 3.13, FastAPI, Pydantic 2, SQLAlchemy Async 및 Alembic 기반 프로젝트 골격
- `GameStatus`, `LeagueType`, `SourceGame`, canonical SHA-256 변경 감지와 revision 모델
- HTTP → CLI → Playwright 순서의 fallback 정책(정상 무경기는 fallback 하지 않음)
- PostgreSQL 테이블 모델/초기 마이그레이션 및 public 조회 API
- `/health/live`, `/health/ready`, `/api/v1/teams`, `/api/v1/games`, `/api/v1/games/{id}`, `/api/v1/results/latest`

KBO의 실제 내부 XHR과 kbocli의 안정적인 JSON 명령 형식은 버전/시점에 따라 확인이 필요합니다. 따라서 확인되지 않은 endpoint·CLI 인자를 코드에 고정하지 않았습니다. `KBO_SCHEDULE_URL`과 전용 parser를 확인한 뒤 `KboHttpSource`에 주입하는 것이 다음 작업입니다.

## 실행

```sh
cp .env.example .env
uv sync --all-groups
uv run alembic upgrade head
uv run python -m app.cli api
```

Swagger UI는 `http://localhost:8000/docs`입니다. Docker에서는 `POSTGRES_PASSWORD`와 `.env`를 설정한 후 `docker compose up --build`로 실행합니다.

## 개발 명령

`make lint`, `make format`, `make type-check`, `make test`, `make check`, `make migrate`를 제공합니다. 실제 KBO 접속 테스트는 `pytest -m live`로 분리해야 합니다.
