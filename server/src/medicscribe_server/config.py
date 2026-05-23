from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MEDICSCRIBE_",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8080
    app_version: str = "0.0.1"

    audio_dir: Path = Path("./data/audio")
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    audio_sample_width: int = 2


settings = Settings()
