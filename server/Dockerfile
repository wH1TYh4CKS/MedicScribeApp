# MedicScribe FastAPI server image — built from server/ context.
#
# App only: no CUDA, no model weights. ASR runs on CPU (see
# llm/models/asr.container.yaml) and note generation is delegated to any
# OpenAI-compatible endpoint you point MEDICSCRIBE_NOTE_ENDPOINT at.
#
# Tests are not run from this image: they read prompt templates from ../llm,
# which lives outside this build context. Run them from the repo root
# (`cd server && pytest`), which is what CI does.
FROM python:3.12-slim AS base
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/cache/huggingface

# ffmpeg: audio resampling for the prep/eval scripts. curl: healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -m app && mkdir -p /cache/huggingface && chown -R app:app /cache

COPY pyproject.toml ./
COPY src/ ./src/


# Runtime image — the default target.
FROM base AS runtime
RUN pip install -e .
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD curl -f http://127.0.0.1:8080/health || exit 1
CMD ["uvicorn", "medicscribe_server.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
