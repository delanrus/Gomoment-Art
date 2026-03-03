from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TELEGRAM_BOT_TOKEN: str
    OPENAI_API_KEY: str
    DEMO_MODE: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"
    PROMPTS_PATH: str = "prompts/cards.yml"
    ADMIN_USER_ID: int | None = None

settings = Settings()

