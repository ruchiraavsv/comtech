from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr("")
    request_timeout_seconds: float = Field(default=60, gt=0, le=300)
    mock_delay_seconds: float = Field(default=0.4, ge=0, le=10)
    git_revision: str = "local"
    observability_mode: Literal["off", "phoenix", "langsmith"] | None = None
    phoenix_project_name: str = "comtech-local"
    phoenix_trace_endpoint: str = "http://localhost:6006/v1/traces"
    trace_hide_inputs: bool = False
    trace_hide_outputs: bool = False
    log_file_enabled: bool = False
    log_directory: Path = Path("var/logs")
    log_max_bytes: int = Field(default=10 * 1024 * 1024, ge=256)
    log_backup_count: int = Field(default=5, ge=1, le=100)
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "comtech-dev"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_workspace_id: str = ""
    langsmith_tracing_sampling_rate: float = Field(default=1, ge=0, le=1)
    pinecone_mode: Literal["hosted", "local"] = "hosted"
    pinecone_api_key: SecretStr = SecretStr("")
    pinecone_index_name: str = ""
    pinecone_index_host: str = ""
    pinecone_local_host: str = "http://localhost:5081"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""

    @model_validator(mode="after")
    def validate_targets(self):
        if self.app_env == "production" and self.pinecone_mode != "hosted":
            raise ValueError("Production requires hosted Pinecone")
        if self.observability_mode in ("off", "phoenix") and self.langsmith_tracing:
            raise ValueError("LANGSMITH_TRACING conflicts with OBSERVABILITY_MODE")
        if self.tracing_mode == "langsmith" and not self.langsmith_api_key.get_secret_value():
            raise ValueError("LANGSMITH_API_KEY is required when tracing is enabled")
        return self

    @property
    def tracing_mode(self) -> str:
        return self.observability_mode or ("langsmith" if self.langsmith_tracing else "off")

    def require_database(self) -> str:
        value = self.database_url.get_secret_value()
        if not value:
            raise ValueError("DATABASE_URL is required")
        return value
