from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str 
    APP_NAME: str = "Forward-Deployed AI Data Harness"
    DEBUG: bool = False
    AUTO_CREATE_TABLES: bool = True
    VALID_FORM_TYPES: list[str] = [
        "bank_statement",
        "athlete_contract",
        "transfer_agreement",
        "sponsorship_endorsement_contract",
    ]
    ROUTER_CONFIDENCE_THRESHOLD: float = 0.7
    PIPELINE_VERSION: str = "2026-09-06.1"
    ROUTER_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EXTRACTION_MODEL: str = "gpt-4o-mini"
    MAX_UPLOAD_BYTES: int = 15 * 1024 * 1024
    DOCUMENT_SOURCE_ROOT: str = ".dist/document-sources"
    DOCUMENT_SOURCE_BACKEND: str = "local"
    AZURE_BLOB_ACCOUNT_URL: str | None = None
    AZURE_BLOB_CONTAINER: str = "document-sources"
    AUTH_MODE: str = "development"
    ENTRA_TENANT_ID: str | None = None
    ENTRA_API_CLIENT_ID: str | None = None
    INGESTION_LEASE_SECONDS: int = 300
    INGESTION_MAX_ATTEMPTS: int = 3
    INGESTION_RETRY_BASE_SECONDS: int = 30
    INGESTION_POLL_SECONDS: float = 2.0
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
