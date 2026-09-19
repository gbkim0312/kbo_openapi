from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://kbo:kbo@postgres:5432/kbo"
    admin_api_key: str = "change-me"
    kbo_base_url: str = "https://www.koreabaseball.com"
    kbo_schedule_url: str = "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList"
    kbo_user_agent: str = "kbo-result-api/0.1"
    kbo_connect_timeout_seconds: float = 5
    kbo_read_timeout_seconds: float = 15
    kbo_total_timeout_seconds: float = 20
    kbo_max_retries: int = 3
    kbo_http_fallback_on_schema_error: bool = True
    kbo_cli_enabled: bool = True
    kbo_playwright_enabled: bool = False
    raw_snapshot_enabled: bool = True
    raw_snapshot_max_bytes: int = 5_242_880
    scheduler_enabled: bool = True
    kbo_refresh_idle_seconds: int = 300
    kbo_refresh_pre_game_seconds: int = 60
    kbo_refresh_live_seconds: int = 15
    kbo_refresh_late_game_seconds: int = 10
    kbo_refresh_failure_backoff_max_seconds: int = 120
    max_query_range_days: int = 31
    default_page_size: int = 50
    max_page_size: int = 200

    @field_validator(
        "kbo_refresh_idle_seconds",
        "kbo_refresh_pre_game_seconds",
        "kbo_refresh_live_seconds",
        "kbo_refresh_late_game_seconds",
        "kbo_refresh_failure_backoff_max_seconds",
        mode="before",
    )
    @classmethod
    def positive_refresh_seconds(cls, value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 300
        return parsed if parsed > 0 else 300


settings = Settings()
