import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app import storage
from app.pipeline import importer
from app.pipeline.cleanup import CleanupOptions
from app.pipeline.normalize import ACCIDENTAL_RULES

router = APIRouter(prefix="/excerpts")

MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _folder(excerpt_id: str) -> Path:
    try:
        return storage.existing_dir(excerpt_id)
    except storage.ExcerptNotFound:
        raise HTTPException(404, "No such excerpt") from None


# A plain `def` so FastAPI runs it in a worker thread; OMR blocks for 10-60 s.
@router.post("", status_code=201)
def create_excerpt(
    file: UploadFile = File(...),
    engine: str = Form("auto"),
    accidental_rule: str = Form("bar"),
    perspective: bool | None = Form(None),
    deskew: bool | None = Form(None),
    threshold: bool | None = Form(None),
) -> dict:
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in importer.SUPPORTED_EXTENSIONS:
        raise HTTPException(415, "Upload a PDF, PNG or JPG")
    if engine not in importer.ENGINE_CHOICES:
        raise HTTPException(422, f"engine must be one of {', '.join(importer.ENGINE_CHOICES)}")
    if accidental_rule not in ACCIDENTAL_RULES:
        raise HTTPException(422, f"accidental_rule must be one of {', '.join(ACCIDENTAL_RULES)}")

    defaults = importer.default_cleanup(extension == ".pdf")
    cleanup = CleanupOptions(
        perspective=defaults.perspective if perspective is None else perspective,
        deskew=defaults.deskew if deskew is None else deskew,
        threshold=defaults.threshold if threshold is None else threshold,
    )

    with tempfile.TemporaryDirectory() as tmp:
        upload = Path(tmp) / f"upload{extension}"
        size = 0
        with upload.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "The file is larger than 100 MB")
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, "The file is empty")
        try:
            return importer.import_excerpt(upload, filename, engine, accidental_rule, cleanup)
        except importer.ImportFailed as err:
            raise HTTPException(422, str(err)) from err


@router.get("")
def list_excerpts() -> list[dict]:
    return storage.list_meta()


@router.get("/{excerpt_id}")
def get_excerpt(excerpt_id: str) -> dict:
    _folder(excerpt_id)
    return storage.read_meta(excerpt_id)


@router.get("/{excerpt_id}/pages/{number}")
def get_page(excerpt_id: str, number: int) -> FileResponse:
    page = _folder(excerpt_id) / "pages" / f"page-{number}.png"
    if number < 1 or not page.is_file():
        raise HTTPException(404, "No such page")
    return FileResponse(page, media_type="image/png")


@router.get("/{excerpt_id}/score")
def get_score(excerpt_id: str, format: str = Query("musicxml", pattern="^(musicxml|mei)$")) -> Response:
    folder = _folder(excerpt_id)
    path = folder / ("score.mei" if format == "mei" else "score.musicxml")
    if not path.is_file():
        raise HTTPException(404, f"No {format} score saved for this excerpt")
    media_type = "application/mei+xml" if format == "mei" else "application/vnd.recordare.musicxml+xml"
    return Response(path.read_bytes(), media_type=media_type)


class ExcerptPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    tempo_bpm: float | None = Field(None, ge=20, le=400)


@router.patch("/{excerpt_id}")
def update_excerpt(excerpt_id: str, patch: ExcerptPatch) -> dict:
    _folder(excerpt_id)
    meta = storage.read_meta(excerpt_id)
    if patch.title is not None:
        title = patch.title.strip()
        if not title:
            raise HTTPException(422, "The title can't be blank")
        meta["title"] = title
    if patch.tempo_bpm is not None:
        meta["tempo_bpm"] = patch.tempo_bpm
        meta["tempo_source"] = "user"
    storage.write_meta(excerpt_id, meta)
    return meta


@router.delete("/{excerpt_id}", status_code=204)
def delete_excerpt(excerpt_id: str) -> None:
    _folder(excerpt_id)
    storage.delete(excerpt_id)
