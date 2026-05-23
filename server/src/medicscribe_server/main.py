from fastapi import FastAPI

from medicscribe_server.api import health
from medicscribe_server.ws import router as ws_router


def create_app() -> FastAPI:
    app = FastAPI(title="MedicScribe", version="0.0.1")
    app.include_router(health.router)
    app.include_router(ws_router.router)
    return app


app = create_app()
