"""Central configuration. All secrets come from .env - never hardcoded."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "retail_dwh"
    postgres_admin_user: str
    postgres_admin_password: str
    dwh_owner_user: str
    dwh_owner_password: str
    dwh_readonly_user: str
    dwh_readonly_password: str

    # --- LLM API ---
    llm_provider: str = "groq"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_api_key: str
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2

    # --- data lake paths ---
    data_dir: Path = PROJECT_ROOT / "data"

    @property
    def bronze_dir(self) -> Path:
        return self.data_dir / "bronze"

    @property
    def silver_dir(self) -> Path:
        return self.data_dir / "silver"

    @property
    def quarantine_dir(self) -> Path:
        return self.data_dir / "quarantine"

    def pg_url(self, user: str, password: str, db: str | None = None) -> str:
        db = db or self.postgres_db
        return (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{db}"
        )

    @property
    def owner_url(self) -> str:
        return self.pg_url(self.dwh_owner_user, self.dwh_owner_password)

    @property
    def readonly_url(self) -> str:
        return self.pg_url(self.dwh_readonly_user, self.dwh_readonly_password)


settings = Settings()
