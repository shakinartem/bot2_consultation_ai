from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    database_url: str = Field(default="sqlite+aiosqlite:///./app.db", alias="DATABASE_URL")

    ai_provider: str = Field(default="fallback", alias="AI_PROVIDER")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.1-8b-instruct:free",
        alias="OPENROUTER_MODEL",
    )
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5:7b", alias="OLLAMA_MODEL")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
