"""The import pipeline: original → page images → cleanup → OMR → normalized MusicXML."""

import shutil
from datetime import datetime, timezone
from pathlib import Path

import cv2

from app import storage
from app.pipeline import omr
from app.pipeline.cleanup import CleanupOptions, clean, load_image
from app.pipeline.normalize import EmptyScoreError, NormalizeResult, normalize
from app.pipeline.omr.base import OMRError
from app.pipeline.pdf import render_pdf

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf"}
ENGINE_CHOICES = ("auto", "audiveris", "homr")


class ImportFailed(RuntimeError):
    """Nothing usable came out of the pipeline. The message is shown to the user."""


def default_cleanup(is_pdf: bool) -> CleanupOptions:
    # PDFs are already flat and straight. Photos get straightened; thresholding stays opt-in.
    return CleanupOptions() if is_pdf else CleanupOptions(perspective=True, deskew=True)


def engine_order(requested: str, is_pdf: bool) -> list[str]:
    if requested == "auto":
        return ["audiveris", "homr"] if is_pdf else ["homr", "audiveris"]
    return [requested]


def import_excerpt(
    source: Path,
    filename: str,
    engine: str = "auto",
    accidental_rule: str = "bar",
    cleanup: CleanupOptions | None = None,
) -> dict:
    """Build an excerpt folder from an uploaded file and return its meta."""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ImportFailed("Upload a PDF, PNG or JPG")
    if engine not in ENGINE_CHOICES:
        raise ImportFailed(f"Unknown engine: {engine}")
    is_pdf = extension == ".pdf"
    cleanup = cleanup or default_cleanup(is_pdf)

    excerpt_id = storage.new_id()
    folder = storage.create_dir(excerpt_id)
    try:
        original = folder / f"original{extension}"
        shutil.copyfile(source, original)

        pages, applied = _prepare_pages(original, folder / "pages", is_pdf, cleanup)
        used, result, warnings = _recognize(pages, folder, engine, is_pdf, accidental_rule)

        meta = {
            "id": excerpt_id,
            "title": Path(filename).stem or "Untitled",
            "original_filename": filename,
            "source_type": "pdf" if is_pdf else "image",
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "page_count": len(pages),
            "engine_requested": engine,
            "engine": used,
            "accidental_rule": accidental_rule,
            "cleanup": cleanup.as_dict(),
            "cleanup_applied": applied,
            "tempo_bpm": result.tempo_bpm,
            "tempo_beat": result.tempo_beat,
            "tempo_source": result.tempo_source,
            "parts": result.parts,
            "playback_part": result.playback_part,
            "measure_count": result.measure_count,
            "note_count": result.note_count,
            "warnings": warnings + result.warnings,
        }
        storage.write_meta(excerpt_id, meta)
        return meta
    except BaseException:
        storage.discard(excerpt_id)
        raise


def _prepare_pages(
    original: Path, pages_dir: Path, is_pdf: bool, cleanup: CleanupOptions
) -> tuple[list[Path], list[str]]:
    try:
        if is_pdf:
            pages = render_pdf(original, pages_dir)
        else:
            pages_dir.mkdir(parents=True, exist_ok=True)
            pages = [pages_dir / "page-1.png"]
            cv2.imwrite(str(pages[0]), load_image(original))
    except ImportFailed:
        raise
    except Exception as err:
        raise ImportFailed(f"Can't read the file: {err}") from err

    applied: set[str] = set()
    if cleanup.any:
        for page in pages:
            image, steps = clean(load_image(page), cleanup)
            if steps:
                cv2.imwrite(str(page), image)
                applied.update(steps)
    return pages, sorted(applied)


def _recognize(
    pages: list[Path], folder: Path, requested: str, is_pdf: bool, accidental_rule: str
) -> tuple[str, NormalizeResult, list[str]]:
    order = engine_order(requested, is_pdf)
    candidates = [name for name in order if omr.ENGINES[name].available()]
    if not candidates:
        missing = " or ".join(order)
        raise ImportFailed(f"{missing} isn't installed. Engine status is shown in the sidebar.")

    omr_dir = folder / "omr"
    omr_dir.mkdir(exist_ok=True)
    failures: list[str] = []
    for name in candidates:
        try:
            raw = omr.ENGINES[name].run(pages, omr_dir)
            result = normalize(raw, folder / "score.musicxml", accidental_rule)
        except (OMRError, EmptyScoreError) as err:
            failures.append(f"{name}: {err}")
            continue
        except Exception as err:  # music21 couldn't parse what the engine wrote
            failures.append(f"{name}: unreadable output ({err})")
            continue
        warnings = [f"{failure.split(':', 1)[0]} failed, so {name} was used instead." for failure in failures]
        return name, result, warnings

    raise ImportFailed("OMR failed.\n" + "\n".join(failures))
