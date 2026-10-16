"""Standalone settings; never reads the application's .env or database settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NORTHSTAR_MCP_", extra="ignore")
    fixture_directory: Path = Path("synthetic_bank/mcp/fixtures")
    host: str = "127.0.0.1"
    port: int = Field(default=8001, ge=1, le=65535)
    lookup_timeout_seconds: float = Field(default=5, gt=0, le=60)
    allowed_hosts: list[str] = ["127.0.0.1:*", "localhost:*", "northstar-mcp:*"]
    allowed_origins: list[str] = [
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://northstar-mcp:*",
    ]
