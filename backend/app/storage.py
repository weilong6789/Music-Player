"""Excerpt folders under data/excerpts/<id>/ with a meta.json each."""

import json
import re
import shutil
import uuid
from pathlib import Path

from app import config

_ID = re.compile(r"^[0-9a-f]{12}$")


class ExcerptNotFound(LookupError):
    pass


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def excerpt_dir(excerpt_id: str) -> Path:
    if not _ID.match(excerpt_id):
        raise ExcerptNotFound(excerpt_id)
    return config.EXCERPTS_DIR / excerpt_id


def existing_dir(excerpt_id: str) -> Path:
    path = excerpt_dir(excerpt_id)
    if not (path / "meta.json").is_file():
        raise ExcerptNotFound(excerpt_id)
    return path


def create_dir(excerpt_id: str) -> Path:
    path = excerpt_dir(excerpt_id)
    path.mkdir(parents=True)
    return path


def write_meta(excerpt_id: str, meta: dict) -> None:
    path = excerpt_dir(excerpt_id) / "meta.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def read_meta(excerpt_id: str) -> dict:
    return json.loads((existing_dir(excerpt_id) / "meta.json").read_text(encoding="utf-8"))


def list_meta() -> list[dict]:
    if not config.EXCERPTS_DIR.is_dir():
        return []
    metas = []
    for path in config.EXCERPTS_DIR.iterdir():
        meta_file = path / "meta.json"
        if _ID.match(path.name) and meta_file.is_file():
            try:
                metas.append(json.loads(meta_file.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return sorted(metas, key=lambda m: m.get("created", ""), reverse=True)


def delete(excerpt_id: str) -> None:
    shutil.rmtree(existing_dir(excerpt_id))


def discard(excerpt_id: str) -> None:
    """Remove a half-built excerpt after a failed import."""
    shutil.rmtree(excerpt_dir(excerpt_id), ignore_errors=True)
