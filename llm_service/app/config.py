from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "LLM Service"
    ENV: str = "dev"

    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "LLM_OPENAI_API_KEY"),
    )
    OPENAI_MODEL: str = "gpt-4o"

    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "LLM_ANTHROPIC_API_KEY"),
    )
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"

    # Gemini / Google
    GOOGLE_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "LLM_GOOGLE_API_KEY"),
    )
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "LLM_GEMINI_API_KEY"),
    )
    GEMINI_API_KEY_2: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY_2", "LLM_GEMINI_API_KEY_2"),
    )

    # Groq
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "LLM_GROQ_API_KEY"),
    )
    GROQ_API_KEY_2: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY_2", "LLM_GROQ_API_KEY_2"),
    )

    # Default provider: openai, anthropic, local
    DEFAULT_PROVIDER: str = Field(
        default="openai",
        validation_alias=AliasChoices("DEFAULT_PROVIDER", "LLM_DEFAULT_PROVIDER"),
    )

    # Service URLs for context injection
    MEMORY_SERVICE_URL: str = "http://memory_service:8000"
    COGNITIVE_SERVICE_URL: str = "http://cognitive_service:8000"
    CHAT_SERVICE_URL: str = "http://chat_service:8000"

    # Redis for caching
    REDIS_URL: str = "redis://redis:6379/0"

    # Rate limiting
    MAX_TOKENS_PER_REQUEST: int = 4096
    MAX_REQUESTS_PER_MINUTE: int = 60

    class Config:
        env_prefix = "LLM_"
        case_sensitive = False


settings = Settings()
