from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "user_service"

    POSTGRES_HOST: str = "user_db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "user_user"
    POSTGRES_PASSWORD: str = "user_pass"
    POSTGRES_DB: str = "user_db"

    class Config:
        env_file = ".env"
        env_prefix = "USER_"
        case_sensitive = False


settings = Settings()

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)
