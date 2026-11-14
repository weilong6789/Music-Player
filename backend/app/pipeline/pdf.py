"""PDF → page PNGs."""

from pathlib import Path

import pymupdf

MAX_PAGES = 20


def render_pdf(pdf_path: Path, out_dir: Path, dpi: int = 300) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pages: list[Path] = []
    with pymupdf.open(pdf_path) as doc:
        if doc.page_count == 0:
            raise ValueError("The PDF has no pages")
        if doc.page_count > MAX_PAGES:
            raise ValueError(
                f"The PDF has {doc.page_count} pages; the limit is {MAX_PAGES}. "
                "Export just the pages with the excerpt."
            )
        for index, page in enumerate(doc, start=1):
            path = out_dir / f"page-{index}.png"
            page.get_pixmap(dpi=dpi, alpha=False).save(path)
            pages.append(path)
    return pages
