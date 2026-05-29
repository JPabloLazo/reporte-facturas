from pydantic_settings import BaseSettings

DEFAULT_IA_PROFILE = "optimized"


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/reporte_facturas.db"
    openrouter_api_key: str = ""
    ia_profile: str = DEFAULT_IA_PROFILE
    google_client_id: str = ""
    google_client_secret: str = ""
    secret_key: str = "change-me-in-production"
    upload_dir: str = "./uploads"

    model_config = {
        "protected_namespaces": ("settings_",),
        "env_file": ".env",
    }


settings = Settings()

from typing import Dict

IA_PROFILES: Dict[str, Dict[str, str]] = {
    "fast": {
        "extraction": "anthropic/claude-sonnet-4",
        "vision": "openai/gpt-4o-2024-05-13",
        "reconciliation": "anthropic/claude-sonnet-4",
        "email": "anthropic/claude-3.5-haiku",
    },
    "optimized": {
        "extraction": "deepseek/deepseek-chat-v3-0324",
        "vision": "openai/gpt-4o-mini",
        "reconciliation": "deepseek/deepseek-chat",
        "email": "openai/gpt-4o-mini",
    },
    "slow": {
        "extraction": "deepseek/deepseek-v3.2",
        "vision": "google/gemini-2.0-flash-lite-001",
        "reconciliation": "deepseek/deepseek-v3.2",
        "email": "meta-llama/llama-3.1-8b-instruct",
    },
    # === TEST ONLY: Perfil gratuito para pruebas ===
    # TODO: Eliminar antes de producción
    "free": {
        "extraction": "openai/gpt-oss-120b",
        "vision": "google/gemma-4-31b-it",
        "reconciliation": "deepseek/deepseek-v4-flash",
        "email": "meta-llama/llama-3.3-70b-instruct",
    },
    # === FIN TEST ONLY ===
}
