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
    # Hard cap on a single recording's length (disk-DoS guard). 0 = unlimited.
    # One appointment = 30 minutes in this build; a real consult ran 21:46 and
    # the old 600s cap would have cut it in half.
    max_recording_seconds: int = 1800
    # Max in-flight WS sessions; excess get a BUSY reject. 0 = unlimited.
    max_concurrent_sessions: int = 8
    # Max in-flight WS sessions per visitor IP; excess get an IP_LIMIT reject.
    # Stops one visitor (or one clinic NAT) from holding every global slot and
    # locking out a clinic via the public page. 2 = headroom for a refresh/stale tab while
    # a consult runs. 0 = unlimited.
    max_sessions_per_ip: int = 2

    # ASR — load whisper at boot. Disable for dev/tests that skip the 6 GB model.
    asr_enabled: bool = True
    asr_config_path: Path = Path("../llm/models/asr.yaml")

    # Note generation
    note_enabled: bool = True
    note_config_path: Path = Path("../llm/models/note_llm.yaml")
    # text-wrapper schema {soap_text: <raw S:/O:/A:/P:>}; matches the
    # response_text_field in note_llm.yaml.
    note_template: str = "sum_v1"
    llm_root: Path = Path("../llm")

    # Recording retention (PDPA): purge WAVs older than this on startup AND on a
    # periodic sweep (so a crash-orphan WAV can't survive a long box uptime).
    recording_ttl_seconds: int = 3600
    reaper_interval_seconds: int = 1800  # 0 disables the periodic sweep

    # Feedback — PRODUCT feedback only, never PHI (the page says so).
    # Appended as JSONL to a local file; no DB, never egresses.
    feedback_dir: Path = Path("./data/feedback")
    feedback_field_max_chars: int = 4000  # per-field cap, disk-DoS guard


settings = Settings()
