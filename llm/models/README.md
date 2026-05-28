# `llm/models/` — Model registry

Each YAML here declares one runtime model. The server reads these at boot and instantiates the matching engine class via `server/src/medicscribe_server/{asr,llm_client}/registry.py`.

## Files

- `asr.yaml` — ASR engine + model (faster-whisper / openai-whisper / whisperx / ...)
- `note_llm.yaml` — note-generation LLM serving stack (vllm / llamacpp / tgi / ...)

## Swap a model — full procedure

1. Edit the relevant YAML. Change `engine` and / or `model_id` and / or `params`.
2. If the new model needs new Python deps → bump `server/pyproject.toml` and rebuild the server image.
3. If the new model is from HuggingFace and gated → set `HF_TOKEN` in `.env`.
4. Restart `medicscribe-server`. Watch logs for `[asr.registry] loaded faster-whisper large-v3` etc.
5. Smoke test `/health` then run a 10 s recording.

## Adding a new engine

1. Create `server/src/medicscribe_server/asr/<your_engine>.py` implementing `ASREngine`.
2. Register it in `server/src/medicscribe_server/asr/registry.py` (add to the `ENGINES` map).
3. Reference it from `asr.yaml` as `engine: <your_engine>`.

## Why YAML and not the .properties file

`project.properties` holds tunables that change per deployment (ports, paths). The model registry holds *what is loaded*, with structured nested params (sampling, gpu_memory_utilization, beam_size). YAML handles nesting cleanly; properties files don't.
