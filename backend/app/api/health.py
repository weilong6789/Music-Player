from fastapi import APIRouter

from app.pipeline.omr import ENGINES

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "engines": {
            name: {"available": engine.available(), "detail": engine.detail()}
            for name, engine in ENGINES.items()
        },
    }
