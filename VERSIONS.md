# MedicScribe — Pinned Versions

Single source of truth for every model + library version. Update this file whenever any pin changes; CI / docker / gradle should read from here (or mirror it).

## Project

| Item        | Version              |
|-------------|----------------------|
| App         | 0.0.1                |
| Codename    | phase0-scaffold      |
| Plan rev    | 1 (witty-chasing-sparkle.md) |

## Models

| Component        | Model                                      | Pinned version / revision | Notes |
|------------------|--------------------------------------------|---------------------------|-------|
| ASR              | `faster-whisper` Whisper-large-v3          | CT2 conv 20240930          | multilingual, no forced lang |
| VAD              | `silero-vad`                               | 5.1                        | CPU, gates ASR |
| Note LLM         | `Qwen/Qwen2.5-14B-Instruct-AWQ`            | 2024-09 AWQ               | Apache-2.0 |
| Note LLM (alt)   | `SeaMLLM/SeaLLM-v3-7B-Chat`                | v3                        | fallback for BM/TA quality |
| Diarization (v1.1)| `pyannote/speaker-diarization-3.1`        | 3.1                        | needs HF token |

## Server (Python 3.11 or 3.12)

| Lib                | Version | Why |
|--------------------|---------|-----|
| python             | 3.11.x or 3.12.x | runtime — `pyproject.toml` pins `>=3.11,<3.13` |
| fastapi            | 0.115.x | ASGI framework |
| uvicorn[standard]  | 0.32.x  | ASGI server |
| pydantic           | 2.9.x   | schemas |
| pydantic-settings  | 2.6.x   | env / properties config |
| faster-whisper     | 1.0.3   | ASR (CTranslate2) |
| ctranslate2        | 4.4.x   | ASR backend |
| silero-vad         | 5.1     | VAD |
| vllm               | 0.6.3   | LLM serving |
| transformers       | 4.46.x  | tokenizer / fallbacks |
| sqlmodel           | 0.0.22  | SQLite ORM |
| jinja2             | 3.1.x   | prompt templates |
| pyannote.audio     | 3.3.x   | diarization (v1.1) |
| outlines           | 0.1.x   | guided JSON decoding (alt to vLLM guided) |
| pytest             | 8.x     | tests |
| ruff               | 0.7.x   | lint/format |
| black              | 24.10.x | format (optional) |

## Android (AGP 8.7 / Kotlin 2.0)

| Item                       | Version |
|----------------------------|---------|
| Android Gradle Plugin      | 8.7.2   |
| Kotlin                     | 2.0.21  |
| Compose BOM                | 2024.10.01 |
| Compose Compiler (k2)      | bundled with Kotlin 2.0 |
| Material 3                 | 1.3.x   |
| Activity Compose           | 1.9.x   |
| Lifecycle / ViewModel      | 2.8.x   |
| kotlinx.coroutines         | 1.9.0   |
| kotlinx.serialization      | 1.7.3   |
| OkHttp                     | 4.12.0  |
| Apache POI (poi-ooxml)     | 5.3.0   |
| AndroidX Core KTX          | 1.13.x  |
| compileSdk / targetSdk     | 34      |
| minSdk                     | 26      |
| JDK (build)                | 17      |

## Infra

| Tool             | Version |
|------------------|---------|
| Docker           | 24+     |
| docker compose   | v2 plugin |
| CUDA             | 12.4    |
| NVIDIA driver    | ≥ 550   |
| nvidia-container-toolkit | latest |

## Update protocol

1. Bump version here first.
2. Then bump in `pyproject.toml` / `build.gradle.kts` / `docker-compose.yml`.
3. Note the change in `CHANGELOG.md` (TBD) under the next release.
4. If a model pin changes → re-run multilingual eval before release.
