from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str 
    APP_NAME: str = "A simple document intelligent system"
    DEBUG: bool = False
    Valid_FORM_TYPES: list[str] = ["bank_statement", "athlete contract", "transfer agreement", "Sponsership & endorsement contract"]
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()
