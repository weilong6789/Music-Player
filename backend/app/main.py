from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.api import excerpts, health

app = FastAPI(title="Excerpt Player")
app.include_router(health.router, prefix="/api")
app.include_router(excerpts.router, prefix="/api")

if config.FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")
else:

    @app.get("/", response_class=PlainTextResponse)
    def frontend_missing() -> str:
        return "Frontend isn't built yet. Run `make start`, or `make dev` and open http://localhost:5173."
