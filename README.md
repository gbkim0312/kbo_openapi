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
- 게임센터 라인업(확정 여부·타순·포지션·WAR)과 공식 프리뷰 분석 수집
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

## API 명세

기본 주소는 `http://localhost:8085`입니다. 모든 공개 조회 API는 인증이 필요 없고, `internal` API는 `Authorization: Bearer {ADMIN_API_KEY}` 헤더가 필요합니다. 상세 스키마와 즉시 실행은 [Swagger UI](http://localhost:8085/docs)에서 확인할 수 있습니다.

| 구분 | Method | Path | 파라미터 / 본문 | 설명 |
| --- | --- | --- | --- | --- |
| 상태 | `GET` | `/health/live` | 없음 | API 프로세스 상태 |
| 상태 | `GET` | `/health/ready` | 없음 | PostgreSQL 연결 상태 |
| 관리 화면 | `GET` | `/admin` | 없음 | 브라우저 기반 API 상태·호출 대시보드 |
| 공개 | `GET` | `/api/v1/teams` | 없음 | 등록된 KBO 팀 목록 |
| 공개 | `GET` | `/api/v1/games` | `date` 또는 `from`·`to`, `team`, `status`, `leagueType`, `limit`, `cursor` | 경기 목록. 기간은 최대 31일이며 `date`와 기간 조건은 함께 사용할 수 없음 |
| 공개 | `GET` | `/api/v1/games/{gameId}` | 내부 경기 ID | 단일 경기 |
| 공개 | `GET` | `/api/v1/results/latest` | `date`, `team`, `limit` | 최신 종료 경기. `date`로 특정 날짜의 종료 경기만 조회 가능 |
| 공개 | `GET` | `/api/v1/rankings` | `date`(선택) | 팀 순위, 승차, 최근 10경기, 연승·연패 |
| 공개 | `GET` | `/api/v1/player-stats` | `season`(필수), `role`, `team`, `limit` | 시즌 타자·투수 기록. `role`: `hitter` 또는 `pitcher` |
| 공개 | `GET` | `/api/v1/awards` | `season`(선택) | KBO 공식 시즌 MVP |
| 공개 | `GET` | `/api/v1/games/{gameId}/details` | 내부 경기 ID | 결승타와 투수별 경기 기록 |
| 공개 | `GET` | `/api/v1/games/{gameId}/lineups` | 내부 경기 ID | 최신 수집 라인업, 타순·포지션·WAR·확정 여부 |
| 공개 | `GET` | `/api/v1/games/{gameId}/analysis` | 내부 경기 ID | KBO 게임센터의 팀 비교·핵심선수 프리뷰 분석 |
| 내부 | `POST` | `/internal/v1/collections/all` | `{"targetDate":"YYYY-MM-DD"}` | 날짜별 경기, 시즌 순위·선수 기록·MVP, 종료 경기 상세 기록을 순차 수집 |
| 내부 | `POST` | `/internal/v1/collections` | `{"targetDate":"YYYY-MM-DD","force":false}` | 날짜별 경기 일정·결과 수집 |
| 내부 | `POST` | `/internal/v1/records/collect` | 없음 | 팀 순위, 타자·투수 시즌 기록, 공식 MVP 수집 |
| 내부 | `POST` | `/internal/v1/games/{gameId}/details/collect` | 내부 경기 ID | 완료 경기의 결승타·투수 기록 수집 |
| 내부 | `POST` | `/internal/v1/games/{gameId}/preview/collect` | 내부 경기 ID | 라인업과 공식 프리뷰 분석 수집 |

`/api/v1/games`의 `score`는 경기 전 `null`, 무득점은 `0`입니다. `cursor`에는 이전 응답의 `meta.nextCursor`를 전달합니다. 잘못된 날짜·기간·페이지 크기는 HTTP 422를, 잘못된 내부 API 토큰은 HTTP 401을 반환합니다.

## API 사용 예시

```sh
# 특정 날짜의 경기와 팀 필터
curl 'http://localhost:8085/api/v1/games?date=2026-08-05&team=SS&limit=20'

# 팀 순위 및 2026년 투수 기록
curl http://localhost:8085/api/v1/rankings
curl 'http://localhost:8085/api/v1/player-stats?season=2026&role=pitcher&limit=20'

# 2026-08-04 종료 경기만 조회
curl 'http://localhost:8085/api/v1/results/latest?date=2026-08-04'

# 날짜별 경기 수집
curl -X POST http://localhost:8085/internal/v1/collections \
  -H "Authorization: Bearer $(grep '^ADMIN_API_KEY=' .env | cut -d= -f2-)" \
  -H 'Content-Type: application/json' \
  -d '{"targetDate":"2026-08-05","force":false}'

# 날짜별 경기·순위·선수 기록·종료 경기 상세를 한 번에 수집
curl -X POST http://localhost:8085/internal/v1/collections/all \
  -H "Authorization: Bearer $(grep '^ADMIN_API_KEY=' .env | cut -d= -f2-)" \
  -H 'Content-Type: application/json' \
  -d '{"targetDate":"2026-08-05"}'

# 내부 경기 ID 2의 라인업·공식 분석을 수집하고 조회
curl -X POST http://localhost:8085/internal/v1/games/2/preview/collect \
  -H "Authorization: Bearer $(grep '^ADMIN_API_KEY=' .env | cut -d= -f2-)"
curl http://localhost:8085/api/v1/games/2/lineups
curl http://localhost:8085/api/v1/games/2/analysis
```

`gameId`는 `sourceGameId`가 아니라 `/api/v1/games` 응답의 숫자 `id`입니다. `lineups.confirmed`가 `true`면 KBO가 확정 라인업으로 표시한 데이터이고, `false`면 확정 전 최근 라인업입니다. `analysis.officialAnalysis`는 KBO 공식 분석 원문 구조이며 자체 승률 예측 모델은 아닙니다.

## 관리 대시보드

`http://서버-IP:8085/admin`에서 API 대시보드를 엽니다. 모든 공개 조회 API와 모든 내부 수집 API에 대해 입력값을 넣고 **API 호출** 버튼으로 응답 JSON을 바로 확인할 수 있습니다. 내부 수집 API를 호출할 때만 화면 상단에 `ADMIN_API_KEY`를 입력합니다. 이 키는 브라우저 저장소에 보관하지 않으며, 해당 요청의 `Authorization` 헤더로만 전송됩니다.

대시보드 자체에는 로그인 기능이 없으므로 인터넷에 직접 공개하지 마세요. OMV 개인 서버에서는 내부망에서만 사용하거나, 외부 접근이 필요하면 역방향 프록시의 인증과 HTTPS를 앞단에 설정하세요.

## 수동 수집과 backfill

컨테이너에서 명령을 직접 실행할 수 있습니다.

```sh
# 날짜 하나 수집
docker compose run --rm kbo-worker collect-date 2026-08-05

# 과거 31일 이내 범위 수집
docker compose run --rm kbo-worker backfill 2026-08-01 2026-08-05

# 팀 순위, 선수 기록, 공식 MVP 수집
docker compose run --rm kbo-worker collect-records
```

`SCHEDULER_ENABLED=true`인 정기 worker는 다음 시간(Asia/Seoul)에 동작합니다.

- 매일 00:30: 전날 경기·팀 순위·선수 기록·MVP·종료 경기 상세 기록 전체 수집
- 매일 06:00, 12:00: 당일 경기 수집
- 16:00~23:59: 15분마다 미확정 경기의 라인업·공식 프리뷰 분석 수집. 확정 라인업을 받으면 해당 경기의 프리뷰 재수집을 중단
- 17:00~23:59: 5분마다 당일 경기 상태·점수 수집 및 진행 중 경기의 투수 상세 기록 갱신

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

## OMV Compose GUI로 서버 배포

`compose.omv.yml`은 OMV의 Compose 플러그인에서 관리하기 위한 서버용 파일입니다. API와 worker 이미지는 서버의 Docker가 현재 프로젝트 폴더에서 직접 빌드하고, Compose 파일과 `.env`는 OMV GUI에서 편집할 수 있습니다. PostgreSQL 데이터는 Docker named volume이 아닌 OMV 공유 폴더에 보관합니다.

1. OMV에서 공유 폴더(예: `appdata/kbo-openapi`)를 만들고, 서버의 절대 경로를 확인합니다.
2. 해당 폴더에 이 저장소를 내려받습니다. Compose 파일의 `build.context: .` 때문에 `Dockerfile`, `app/`, `migrations/`가 같은 프로젝트 폴더에 있어야 합니다.
3. OMV Compose GUI에서 프로젝트를 만들고, Compose 파일 내용으로 [compose.omv.yml](compose.omv.yml)을 붙여 넣습니다. GUI의 작업 디렉터리는 저장소 최상위 폴더로 지정합니다.
4. 같은 GUI 프로젝트의 `.env`에 [`.env.example`](.env.example)을 복사한 뒤 아래 값만 반드시 실제 값으로 교체합니다.

```dotenv
POSTGRES_PASSWORD=긴-DB-비밀번호
ADMIN_API_KEY=긴-관리-API-키
KBO_POSTGRES_DATA_DIR=/srv/dev-disk-by-uuid-xxxx/appdata/kbo-openapi/postgres
KBO_API_PORT=8085
SCHEDULER_ENABLED=true
```

`KBO_POSTGRES_DATA_DIR`는 반드시 빈 전용 폴더 또는 이 서비스가 이미 사용 중인 PostgreSQL 데이터 폴더여야 합니다. OMV의 파일 관리자에서 이 폴더를 먼저 만들고, Docker가 쓸 수 있는 권한을 부여하세요. 데이터 초기화가 필요할 때는 컨테이너가 중지된 상태에서 이 폴더의 내용을 삭제해야 하므로 주의하세요.

5. OMV GUI에서 **Build** 후 **Up**을 실행합니다. `kbo-migrate`가 먼저 DB 마이그레이션을 적용한 후 종료되고, 성공해야 `kbo-api`와 `kbo-worker`가 시작됩니다. `kbo-migrate`의 종료 상태 `0`은 정상입니다.
6. `http://서버-IP:8085/health/ready` 또는 OMV 로그에서 준비 상태를 확인합니다. 외부 공개가 필요 없으면 공유기 포트포워딩을 만들지 말고, 필요하면 역방향 프록시와 HTTPS를 별도로 설정하세요.

서버에서 Git으로 업데이트한 뒤에는 OMV GUI에서 **Pull**(또는 터미널의 `git pull`) → **Build** → **Up** 순으로 실행하면 됩니다. 새 DB 마이그레이션도 `kbo-migrate`가 자동 적용합니다.

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
