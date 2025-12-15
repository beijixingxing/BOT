from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Discord
    discord_bot_token: str = ""
    
    # Backend
    backend_url: str = "http://localhost:8000"
    
    # Bot ID (用于多Bot区分)
    bot_id: str = "default"
    
    # LLM (通用配置，可在Web后台修改)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    
    # Context (Bot独立配置，可在Web后台修改)
    context_limit: int = 10
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./catiebot.db"
    
    # Admin
    admin_password: str = "change_this_to_a_secure_secret"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
