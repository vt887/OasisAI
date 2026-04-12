from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    service_name: str = "oasis-service"
    log_level: str = "INFO"

    ollama_url: str = "http://ollama:11434"
    chroma_path: str = "/data/chroma"
    chroma_host: str = "chroma"
    chroma_port: int = 8000
    chroma_collection: str = "oasis_code"

    llm_url: str = "http://llm:8001"
    agent_url: str = "http://agent:8004"
    graph_url: str = "http://graph:8003"
    indexer_url: str = "http://indexer:8002"
    gateway_url: str = "http://gateway:8080"

    request_timeout_seconds: float = 240.0
    readiness_timeout_seconds: float = 5.0
    retries: int = 3
    backoff_seconds: float = 0.5

    cache_enabled: bool = True
    cache_ttl_seconds: int = 15
    embed_cache_size: int = 4096

    default_model: str = "codellama"
    embed_model: str = "nomic-embed-text"

    chunk_size: int = 60
    chunk_overlap: int = 10
    batch_size: int = 32
    max_workers: int = 8
    http_client_timeout_seconds: float = 240.0
    chroma_anonymized_telemetry: bool = False


settings = Settings()
