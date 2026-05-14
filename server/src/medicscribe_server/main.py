from fastapi import FastAPI

from medicscribe_server.api import health


def create_app() -> FastAPI:
    app = FastAPI(title="MedicScribe", version="0.0.1")
    app.include_router(health.router)
    return app


app = create_app()
