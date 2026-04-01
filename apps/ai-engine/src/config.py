"""Application configuration using Pydantic Settings for type-safe env var parsing."""

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class LogFormat(str, Enum):
    """Log output formats."""

    JSON = "json"
    CONSOLE = "console"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Configuration
    llm_service: LLMProvider = Field(
        default=LLMProvider.GEMINI,
        description="Cloud LLM provider to use",
    )
    llm_model: str = Field(
        default="gemini-2.0-flash",
        description="Model identifier for the selected provider",
    )
    llm_api_key: str = Field(
        default="",
        description="API key for the LLM provider",
    )

    # Rate Limiting Configuration
    llm_max_concurrency: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum concurrent LLM requests",
    )
    llm_max_retries: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum retry attempts for failed requests",
    )
    llm_retry_min_wait: float = Field(
        default=1.0,
        ge=0.1,
        description="Minimum wait time (seconds) between retries",
    )
    llm_retry_max_wait: float = Field(
        default=60.0,
        ge=1.0,
        description="Maximum wait time (seconds) between retries",
    )

    # Neo4j Configuration
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j Bolt connection URI",
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username",
    )
    neo4j_password: str = Field(
        default="",
        description="Neo4j password",
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: LogFormat = Field(
        default=LogFormat.JSON,
        description="Log output format",
    )

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    grpc_port: int = Field(default=50051, ge=1, le=65535, description="gRPC server port")


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings singleton."""
    return Settings()
