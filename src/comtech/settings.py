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
    pinecone_cloud: Literal["aws", "gcp", "azure"] = "aws"
    pinecone_region: str = "us-east-1"
    pinecone_namespace_budget: int = Field(default=100, gt=0)
    pinecone_local_host: str = "http://localhost:5081"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = Field(default=1536, gt=0)
    ingestion_source_root: Path = Path("synthetic_bank/corpus")
    ingestion_artifact_root: Path = Path("var/ingestion")
    agent_mode: Literal["mock", "enterprise"] = "mock"
    background_enabled: bool = False
    research_enabled: bool = False
    research_broker_url: str = "http://research-broker:8002"
    research_api_url: str = "http://api:8000"
    research_service_token: SecretStr = SecretStr("")
    research_runner_socket: Path = Path("/run/research-control/runner.sock")
    research_artifact_root: Path = Path("/var/research/artifacts")
    research_maintenance_seconds: float = Field(default=300, ge=1)
    objective_timeout_seconds: float = Field(default=1800, gt=0)
    objective_finalization_seconds: float = Field(default=180, gt=0)
    event_follow_seconds: float = Field(default=60, gt=0, le=300)
    agent_build_id: str = "2fddb22824bee702"
    agent_mcp_url: str = "http://northstar-mcp:8001/mcp"
    agent_token_encoding: str = "o200k_base"
    agent_model_context_window: int = Field(default=128000, ge=30000)
    agent_model_timeout_seconds: float = Field(default=45, gt=0)
    supervisor_model: str = ""
    knowledge_worker_model: str = ""
    knowledge_worker_complex_model: str = ""
    reviewer_model: str = ""
    final_answer_model: str = ""
    max_sections_per_read: int = Field(default=3, ge=1)
    max_tokens_per_section: int = Field(default=1000, ge=64)
    max_tokens_per_read: int = Field(default=3000, ge=512)
    knowledge_worker_max_cycles: int = Field(default=5, ge=1)
    total_context_budget: int = Field(default=30000, ge=4000)
    finalization_reserve: int = Field(default=4000, ge=1000)
    max_review_cycles: int = Field(default=2, ge=1)
    agent_max_tasks: int = Field(default=6, ge=1)
    agent_parallel_workers: int = Field(default=1, ge=1, le=4)
    agent_tool_timeout_seconds: float = Field(default=15, gt=0)
    agent_worker_timeout_seconds: float = Field(default=90, gt=0)

    @model_validator(mode="after")
    def validate_targets(self):
        if self.objective_finalization_seconds >= self.objective_timeout_seconds:
            raise ValueError("Objective deadline must protect finalization time")
        if self.background_enabled and self.agent_mode != "enterprise":
            raise ValueError("Background execution requires enterprise mode")
        if self.research_enabled and (
            not self.background_enabled or len(self.research_service_token.get_secret_value()) < 32
        ):
            raise ValueError("Research requires background mode and a private service token")
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
