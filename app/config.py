from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    database_url: str = Field(default="sqlite+aiosqlite:///./app.db", alias="DATABASE_URL")
    api_token: str = Field(default="", alias="API_TOKEN")
    api_auth_enabled: bool = Field(default=False, alias="API_AUTH_ENABLED")

    ai_provider: str = Field(default="fallback", alias="AI_PROVIDER")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.1-8b-instruct:free",
        alias="OPENROUTER_MODEL",
    )
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5:7b", alias="OLLAMA_MODEL")

    crm_adapter: str = Field(default="mock", alias="CRM_ADAPTER")
    crm_api_base_url: str = Field(default="http://localhost:8001", alias="CRM_API_BASE_URL")
    crm_api_token: str = Field(default="", alias="CRM_API_TOKEN")
    crm_ready_statuses: str = Field(
        default="consultation_planned,consultation_scheduled",
        alias="CRM_READY_STATUSES",
    )
    crm_shared_database_url: str = Field(
        default="sqlite+aiosqlite:///../bot1_crm/app.db",
        alias="CRM_SHARED_DATABASE_URL",
    )

    pdf_export_enabled: bool = Field(default=False, alias="PDF_EXPORT_ENABLED")
    pdf_export_provider: str = Field(default="none", alias="PDF_EXPORT_PROVIDER")

    storage_path: Path = Field(default=Path("./storage"), alias="STORAGE_PATH")
    admin_ids: str = Field(default="", alias="ADMIN_IDS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def admin_id_set(self) -> set[int]:
        values: set[int] = set()
        for item in self.admin_ids.split(","):
            item = item.strip()
            if item.isdigit():
                values.add(int(item))
        return values

    @property
    def crm_ready_status_list(self) -> list[str]:
        return [item.strip() for item in self.crm_ready_statuses.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
