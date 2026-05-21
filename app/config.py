from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/reporte_facturas.db"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    default_llm_provider: str = "anthropic"
    model_extraction: str = "claude-3-5-sonnet-20241022"
    model_vision: str = "gpt-4o"
    model_reconciliation: str = "gpt-4o-mini"
    model_email: str = "claude-3-5-sonnet-20241022"
    google_client_id: str = ""
    google_client_secret: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_responsable: str = ""
    secret_key: str = "change-me-in-production"
    upload_dir: str = "./uploads"

    model_config = {
        "protected_namespaces": ("settings_",),
        "env_file": ".env",
    }


settings = Settings()
