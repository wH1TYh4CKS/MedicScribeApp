# MedicScribe FastAPI server image — built from server/ context.
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN useradd -u 1000 -m app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://127.0.0.1:8080/health || exit 1
CMD ["uvicorn", "medicscribe_server.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
