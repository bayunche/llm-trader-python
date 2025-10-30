"""FastAPI 应用实例。"""

from __future__ import annotations

from fastapi import FastAPI

from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Trader API", version="0.1.0")
    app.include_router(router, prefix="/api")
    return app


app = create_app()
