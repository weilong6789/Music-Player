from app.pipeline.omr.audiveris import AudiverisEngine
from app.pipeline.omr.base import OMREngine
from app.pipeline.omr.homr import HomrEngine

ENGINES: dict[str, OMREngine] = {
    engine.name: engine for engine in (AudiverisEngine(), HomrEngine())
}

__all__ = ["ENGINES", "OMREngine", "AudiverisEngine", "HomrEngine"]
