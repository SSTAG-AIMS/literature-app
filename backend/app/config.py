from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_ENV = APP_DIR.parent.parent / ".env"
BACKEND_ROOT_ENV = APP_DIR.parent / ".env"
ENV_FILE = str(PROJECT_ROOT_ENV if PROJECT_ROOT_ENV.exists() else BACKEND_ROOT_ENV)

class Settings(BaseSettings):
    database_url: str
    ollama_url: str = "http://localhost:11434"
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8")
    unpaywall_email: str = "kadir55301102@gmail.com"  # .env ile override edilir
    eager_pdf_download: bool = False   
settings = Settings()
