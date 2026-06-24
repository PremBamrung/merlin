"""
Centralised configuration using Pydantic Settings.
All environment variables are defined here — single source of truth.
LLM instances are lazily created to avoid import-time failures.
"""

from functools import cached_property
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = f"sqlite:///{Path(__file__).parent.parent / 'merlin.db'}"
    # SQLite journal mode. WAL is best for native runs, but is UNSAFE on a macOS
    # Docker bind mount (mmap/-shm + fsync semantics don't survive the VM↔host
    # boundary, so committed-but-uncheckpointed writes can be lost on restart).
    # The Docker .env overrides this to DELETE, which commits straight into the
    # main .db file.
    sqlite_journal_mode: str = "WAL"

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_model_deployment: str = ""

    # OpenRouter (alternative LLM)
    openrouter_api_key: str = ""
    openrouter_model_deployment: str = ""
    openrouter_endpoint: str = "https://openrouter.ai/api/v1"

    # Agentic chat (Pydantic AI). The chat agent runs on OpenRouter independently
    # of `settings.llm` (the summariser). `chat_model` is an optional override;
    # it falls back to `openrouter_model_deployment` so no new required config.
    # The chosen model MUST support tool-calling (a reasoning model surfaces a
    # `reasoning` part in the UI; a standard one shows only the tool trace).
    chat_model: str = ""
    # Per-turn budget of agent model-requests. On the final allowed request the
    # tools are withdrawn and the model is told to answer from what it has (see
    # merlin.rag.agent) — so a long search ends with a graceful answer, not an
    # error. Also the hard loop/runaway guard.
    chat_max_requests: int = 20

    @property
    def chat_model_name(self) -> str:
        """Model id for the chat agent — explicit override or OpenRouter default."""
        return self.chat_model or self.openrouter_model_deployment

    # Groq (audio transcription fallback)
    groq_api_key: str = ""
    # Max upload size for Groq's /audio/transcriptions endpoint. Files above
    # this are split into chunks and transcribed separately. Groq's hard limit
    # is 25 MB (free) / 100 MB (dev); keep a margin below 25.
    groq_max_upload_mb: float = 24.0
    # Chunk length (seconds) when an audio file exceeds groq_max_upload_mb.
    groq_audio_chunk_seconds: int = 600

    # Active LLM provider: "azure" | "openrouter"
    llm_provider: str = "azure"

    # Embeddings / reranking (hybrid semantic search — see
    # docs/CHAT_AGENT_RETRIEVAL_PLAN.md "Fix 3" + docs/JINA_API_REFERENCE.md).
    # "none" → NullEmbedder (pure FTS5, the historical behaviour); "jina" → Jina
    # cloud embeddings + reranking. Built lazily via merlin.rag.embeddings; the
    # whole vector arm degrades to FTS5-only when the provider is absent/errors.
    embedding_provider: str = "none"
    jina_api_key: str = ""
    jina_embedding_model: str = "jina-embeddings-v5-text-small"
    jina_reranker_model: str = "jina-reranker-v3"
    # Minimum seconds between Jina calls, enforced process-wide across the ingest
    # worker threads (the same burst guard as youtube_subtitle_min_interval).
    # 0 = no throttling (default). Set this on a free key (≈100 RPM / 2 concurrent
    # requests) — e.g. 0.7 keeps bulk ingest comfortably under the cap. The
    # interactive search path is unaffected unless it actually bursts, since the
    # limiter only blocks when calls land closer together than this interval.
    jina_min_interval: float = 0.0
    # On app startup, spawn a background thread that embeds any completed item
    # missing a vector (the backlog + ingest-time failures). Idempotent and cheap
    # when nothing is missing; a no-op when no provider is configured. Set false
    # to disable the auto-heal and rely solely on scripts/backfill_embeddings.py.
    embedding_auto_heal: bool = True

    # App
    app_password: str = ""
    log_level: str = "INFO"

    # YouTube subtitle fetching — minimum seconds between requests to
    # YouTube's transcript endpoint (across all ingest workers), to avoid
    # being temporarily IP-banned (HTTP 429) during bulk ingestion.
    youtube_subtitle_min_interval: float = 10.0
    # When YouTube blocks the transcript endpoint (HTTP 429 / IP block), pause
    # all subtitle fetching for this long so the IP can recover; ingestion falls
    # back to audio transcription meanwhile. Repeated blocks (with no successful
    # fetch in between) escalate the pause by doubling, up to the _max cap.
    youtube_subtitle_cooldown: float = 1800.0  # 30 minutes
    youtube_subtitle_cooldown_max: float = 7200.0  # 2 hour escalation cap

    @cached_property
    def llm(self):
        """Lazily create the LLM instance based on active provider."""

        from langchain_openai import AzureChatOpenAI, ChatOpenAI

        if self.llm_provider == "openrouter":
            if not self.openrouter_api_key:
                raise ValueError(
                    "OPENROUTER_API_KEY is required for OpenRouter provider"
                )
            return ChatOpenAI(
                model=self.openrouter_model_deployment,
                base_url=self.openrouter_endpoint,
                api_key=self.openrouter_api_key,
                temperature=0.01,
                max_tokens=None,
                streaming=True,
            )
        else:
            # Azure OpenAI (default)
            missing = [
                v
                for v, val in [
                    ("AZURE_OPENAI_ENDPOINT", self.azure_openai_endpoint),
                    ("AZURE_OPENAI_KEY", self.azure_openai_key),
                    ("AZURE_MODEL_DEPLOYMENT", self.azure_model_deployment),
                ]
                if not val
            ]
            if missing:
                raise ValueError(f"Missing Azure OpenAI env vars: {', '.join(missing)}")
            return AzureChatOpenAI(
                deployment_name=self.azure_model_deployment,
                azure_endpoint=self.azure_openai_endpoint,
                api_key=self.azure_openai_key,
                openai_api_version=self.azure_openai_api_version,
                temperature=0.01,
                max_tokens=None,
                streaming=True,
            )

    @property
    def llm_model_name(self) -> str:
        if self.llm_provider == "openrouter":
            return self.openrouter_model_deployment
        return self.azure_model_deployment


settings = Settings()
