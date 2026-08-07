from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FOD Smart Toolbox API"
    app_env: str = "development"
    database_url: str = "mysql+pymysql://esp_user:esp_password@127.0.0.1:3306/esp_toolbox?charset=utf8mb4"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    device_api_key: str = ""

    # Admin login
    admin_username: str = "10001"
    admin_password: str = "wearethechampion"
    secret_key: str = "change-this-secret-key-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    llm_provider: str = "ppio"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    # 多模态视觉模型：用于损坏检测看图写报告。缺省复用 LLM_API_KEY / LLM_BASE_URL。
    llm_vision_model: str = "moonshotai/kimi-k3"
    llm_vision_api_key: str = ""
    llm_vision_base_url: str = ""

    damage_model_url: str = ""
    damage_model_api_key: str = ""
    damage_model_timeout: float = 20.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
