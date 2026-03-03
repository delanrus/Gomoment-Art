from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TELEGRAM_BOT_TOKEN: str
    OPENAI_API_KEY: str
    # DEMO_MODE: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"
    PROMPTS_PATH: str = "prompts/cards.yml"
    ADMIN_USER_ID: int | None = 81262886
    TELEGRAM_BOT_ID: int | None = 8608217593
    WELCOME_MEDIA_TYPE: str | None = None  # photo | video
    WELCOME_MEDIA_FILE_ID: str | None = None
    WELCOME_MEDIA_STORE_PATH: str = "data/welcome_media.json"

settings = Settings()


