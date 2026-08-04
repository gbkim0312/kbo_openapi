# KBO 경기 결과 OpenAPI

KBO 경기 일정과 결과를 KBO 공식 사이트에서 수집해 PostgreSQL에 저장하고, REST API로 조회하는 개인용 서비스입니다.

API 조회 요청은 KBO 사이트에 직접 접속하지 않습니다. Worker 또는 수동 수집 명령이 KBO 데이터를 받아 DB에 저장하고, API는 저장된 데이터만 반환합니다.

```text
KBO 공식 일정 응답 → 수집/정규화 → PostgreSQL → REST API / Swagger
```

## 제공 기능

- KBO 공식 일정 XHR(`GetScheduleList`)에서 정규 시즌 일정·결과 수집
- 팀, 상태, 점수, 경기 시각(Asia/Seoul) 정규화
- 원본 응답(raw snapshot) 보존
- 같은 경기를 재수집해도 중복 없이 저장
- 점수·상태 등이 바뀌면 revision과 변경 이력 생성
- 수동 날짜 수집, 31일 이내 backfill, 정기 수집 worker
- Swagger UI 및 공개 조회 API

## 시작 전 준비

가장 간단한 실행 방법은 Docker Desktop입니다.

- Docker Desktop 또는 Docker Engine + Docker Compose v2
- Git
- 인터넷 연결(KBO 공식 사이트 접속용)

Docker 없이 실행하려면 Python 3.13 이상과 [uv](https://docs.astral.sh/uv/)가 필요합니다.

## Docker로 처음 실행하기

### 1. 환경 파일 만들기

```sh
cp .env.example .env
```

`.env`에서 최소한 다음 두 값을 변경합니다.

```dotenv
POSTGRES_PASSWORD=충분히-긴-로컬-비밀번호
ADMIN_API_KEY=관리-API에-사용할-긴-비밀키
```

`POSTGRES_PASSWORD`는 PostgreSQL 컨테이너용 비밀번호이고, `ADMIN_API_KEY`는 수집 요청을 보호합니다. `.env`는 Git에 포함되지 않습니다.

Docker Compose는 `POSTGRES_PASSWORD`를 DB 연결 URL에도 자동으로 사용합니다. Docker 없이 실행할 때만 `DATABASE_URL` 안의 비밀번호도 같은 값으로 바꾸세요.

### 2. DB만 먼저 실행하기

```sh
docker compose up -d postgres
docker compose ps
```

`postgres` 상태가 `healthy`가 될 때까지 잠시 기다립니다.

### 3. DB 구조와 초기 팀 데이터 생성하기

처음 한 번만 실행합니다.

```sh
docker compose run --rm kbo-api migrate
```

이 명령은 `teams`, `games`, `game_revisions`, `raw_snapshots`, `collection_jobs` 테이블과 KBO 10개 구단 데이터를 만듭니다. DB 볼륨을 지우지 않는 한 다시 실행해도 안전합니다.

### 4. API와 수집 worker 시작하기

```sh
docker compose up -d --build
docker compose ps
```

브라우저에서 다음 주소를 엽니다.

- Swagger UI: <http://localhost:8085/docs>
- 생존 확인: <http://localhost:8085/health/live>
- DB 준비 확인: <http://localhost:8085/health/ready>

`ready`가 `{"status":"ok"}`이면 API가 DB에 연결된 상태입니다.

### 5. 처음 데이터를 수집하기

Worker의 정기 수집 시간을 기다리지 않고, 관리 API로 원하는 날짜를 수집할 수 있습니다.

```sh
curl -X POST http://localhost:8085/internal/v1/collections \
  -H "Authorization: Bearer $(grep '^ADMIN_API_KEY=' .env | cut -d= -f2-)" \
  -H 'Content-Type: application/json' \
  -d '{"targetDate":"2026-08-05","force":false}'
```

응답의 `insertedCount`, `updatedCount`, `unchangedCount`를 확인합니다. 수집 날짜는 `YYYY-MM-DD` 형식입니다.

## 데이터 조회 방법

수집 이후에는 인증 없이 조회 API를 사용할 수 있습니다.

```sh
# 등록된 KBO 팀 목록
curl http://localhost:8085/api/v1/teams

# 특정 날짜의 경기
curl 'http://localhost:8085/api/v1/games?date=2026-08-05'

# 기간 조회(기본 최대 31일)
curl 'http://localhost:8085/api/v1/games?from=2026-08-01&to=2026-08-05'

# 팀 코드로 필터링: 삼성(SS), LG(LG), 한화(HH), SSG(SK) 등
curl 'http://localhost:8085/api/v1/games?date=2026-08-05&team=SS'

# 단일 경기
curl http://localhost:8085/api/v1/games/123

# 가장 최근 종료된 경기
curl 'http://localhost:8085/api/v1/results/latest?limit=10'
```

경기 목록은 `scheduledAt`, `id` 순으로 정렬됩니다. `score.away`와 `score.home`은 경기 전에는 `null`일 수 있으며, 0점과 구분됩니다.

## 수동 수집과 backfill

컨테이너에서 명령을 직접 실행할 수 있습니다.

```sh
# 날짜 하나 수집
docker compose run --rm kbo-worker collect-date 2026-08-05

# 과거 31일 이내 범위 수집
docker compose run --rm kbo-worker backfill 2026-08-01 2026-08-05
```

정기 worker는 다음 시간(Asia/Seoul)에 동작합니다.

- 매일 00:10: 전날 경기 재수집
- 매일 06:00, 12:00: 당일 경기 수집
- 17:00~23:59: 5분마다 당일 경기 재수집

정기 수집을 끄려면 `.env`에서 `SCHEDULER_ENABLED=false`로 변경한 뒤 worker를 재시작합니다.

## 환경 변수

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | 없음 | PostgreSQL 비밀번호. 반드시 설정 |
| `DATABASE_URL` | `postgresql+asyncpg://kbo:kbo@postgres:5432/kbo` | API/worker DB 연결 |
| `ADMIN_API_KEY` | `change-me` | 내부 수집 API Bearer 토큰 |
| `KBO_SCHEDULE_URL` | 공식 KBO 일정 endpoint | 수집 endpoint |
| `KBO_MAX_RETRIES` | `3` | 일시적 통신 실패 재시도 횟수 |
| `RAW_SNAPSHOT_ENABLED` | `true` | 원본 응답 보관 여부 |
| `RAW_SNAPSHOT_MAX_BYTES` | `5242880` | 원본 응답 최대 저장 크기 |
| `SCHEDULER_ENABLED` | `true` | worker 정기 수집 활성화 |
| `MAX_QUERY_RANGE_DAYS` | `31` | 경기 기간 조회 최대 일수 |

## 서비스 관리

```sh
# 로그 보기
docker compose logs -f kbo-api
docker compose logs -f kbo-worker

# 중지(데이터는 유지)
docker compose down

# 재시작
docker compose up -d

# 데이터까지 완전히 초기화 — 수집 데이터가 모두 사라짐
docker compose down -v
```

포트 `8085`는 기본적으로 호스트에 공개됩니다. 개인 PC에서만 쓸 경우 공유기 포트포워딩을 설정하지 마세요.

## Docker 없이 실행하기

PostgreSQL을 별도로 준비한 뒤 `.env`의 `DATABASE_URL`을 그 DB에 맞게 바꿉니다.

```sh
uv sync --all-groups
uv run python -m app.cli migrate
uv run python -m app.cli api
```

다른 터미널에서 worker를 실행합니다.

```sh
uv run python -m app.cli worker
```

## 개발 및 검증

```sh
make lint
make type-check
make test
make check
```

parser contract test는 저장된 KBO 응답 fixture를 사용하므로 외부 사이트 없이 실행됩니다. 실제 KBO 통신은 수동 수집 또는 live test에서만 확인합니다.

## 문제 해결

`Cannot connect to the Docker daemon` 오류는 Docker Desktop이 실행되지 않은 상태입니다. Docker Desktop을 시작한 뒤 다시 실행하세요.

`/health/ready`가 실패하면 PostgreSQL 컨테이너 상태(`docker compose ps`)와 `.env`의 `DATABASE_URL`을 확인하세요.

수집이 실패하면 `docker compose logs kbo-api` 또는 `docker compose logs kbo-worker`를 확인하세요. KBO 사이트의 응답 구조가 바뀌면 parser contract test 또는 수집 로그에 schema 관련 오류가 기록됩니다.
