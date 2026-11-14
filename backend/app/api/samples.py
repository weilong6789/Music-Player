import json
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import config

router = APIRouter(prefix="/samples")

_INSTRUMENT = re.compile(r"^[a-z]+$")
_FILE = re.compile(r"^[A-G][#b]?\d\.wav$")


def _index(instrument: str) -> dict[str, str]:
    """Note name → file name, limited to files that are actually there."""
    folder = config.DATA_DIR / "samples" / instrument
    try:
        index = json.loads((folder / "index.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        note: name
        for note, name in index.items()
        if isinstance(name, str) and _FILE.match(name) and (folder / name).is_file()
    }


@router.get("")
def list_samples() -> dict:
    notes = _index("violin")
    return {
        "violin": {
            "available": bool(notes),
            "base_url": "/api/samples/violin/",
            "notes": notes,
        }
    }


@router.get("/{instrument}/{name}")
def get_sample(instrument: str, name: str) -> FileResponse:
    if not _INSTRUMENT.match(instrument) or not _FILE.match(name):
        raise HTTPException(404, "No such sample")
    path = config.DATA_DIR / "samples" / instrument / name
    if not path.is_file():
        raise HTTPException(404, "No such sample")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "max-age=86400"})
