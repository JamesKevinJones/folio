from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "apps" / "companion").exists():
            return parent
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists():
        return cwd
    return here.parents[1]


ROOT = _find_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8787

    google_api_key: str = ""
    openai_api_key: str = ""
    tavily_api_key: str = ""

    llm_model: str = "gemini-flash-latest"
    stt_model: str = "whisper-1"
    tts_model: str = "tts-1"
    tts_voice: str = "nova"

    data_dir: Path = ROOT / "data"
    companion_dist: Path = ROOT / "apps" / "companion" / "dist"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "sessions").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "briefs").mkdir(parents=True, exist_ok=True)
    return settings
