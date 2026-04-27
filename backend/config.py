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

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_model_deployment: str = ""

    # OpenRouter (alternative LLM)
    openrouter_api_key: str = ""
    openrouter_model_deployment: str = ""
    openrouter_endpoint: str = "https://openrouter.ai/api/v1"

    # Groq (audio transcription fallback)
    groq_api_key: str = ""

    # Active LLM provider: "azure" | "openrouter"
    llm_provider: str = "azure"

    # App
    app_password: str = ""
    log_level: str = "INFO"

    @cached_property
    def llm(self):
        """Lazily create the LLM instance based on active provider."""
        import time

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
