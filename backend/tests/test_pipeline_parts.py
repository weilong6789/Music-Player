import zipfile

import cv2
import numpy as np
import pymupdf
import pytest
from music21 import converter

from app.pipeline import cleanup
from app.pipeline.merge import merge_musicxml
from app.pipeline.omr.util import natural_key, read_musicxml
from app.pipeline.pdf import MAX_PAGES, render_pdf
from conftest import make_score, n, write_xml


def staff_page(width=1200, height=900) -> np.ndarray:
    page = np.full((height, width), 255, np.uint8)
    for top in (150, 400, 650):
        for line in range(5):
            y = top + line * 16
            cv2.line(page, (80, y), (width - 80, y), 0, 2)
    return page


# --- pdf -------------------------------------------------------------------


def make_pdf(path, pages=1):
    doc = pymupdf.open()
    for index in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"page {index + 1}")
    doc.save(path)
    doc.close()
    return path


def test_render_pdf_at_300_dpi(tmp_path):
    pages = render_pdf(make_pdf(tmp_path / "in.pdf", pages=2), tmp_path / "pages")
    assert [p.name for p in pages] == ["page-1.png", "page-2.png"]
    height, width = cv2.imread(str(pages[0])).shape[:2]
    assert (width, height) == pytest.approx((595 * 300 / 72, 842 * 300 / 72), abs=1)


def test_render_pdf_rejects_long_documents(tmp_path):
    with pytest.raises(ValueError, match="limit"):
        render_pdf(make_pdf(tmp_path / "in.pdf", pages=MAX_PAGES + 1), tmp_path / "pages")


# --- cleanup ---------------------------------------------------------------


@pytest.mark.parametrize("angle", [-3.0, 2.0, 6.0])
def test_deskew_straightens_staff_lines(angle):
    skewed = cleanup.rotate(staff_page(), angle)
    assert abs(cleanup.estimate_skew(skewed)) == pytest.approx(abs(angle), abs=0.3)

    cleaned, applied = cleanup.clean(skewed, cleanup.CleanupOptions(deskew=True))
    assert applied == ["deskew"]
    assert abs(cleanup.estimate_skew(cleaned)) < 0.3


def test_deskew_leaves_straight_pages_alone():
    cleaned, applied = cleanup.clean(staff_page(), cleanup.CleanupOptions(deskew=True))
    assert applied == []


def test_no_options_returns_the_image_untouched():
    page = cv2.cvtColor(staff_page(), cv2.COLOR_GRAY2BGR)
    cleaned, applied = cleanup.clean(page, cleanup.CleanupOptions())
    assert cleaned is page and applied == []


def test_threshold_gives_a_binary_image():
    shaded = (staff_page().astype(np.float32) * np.linspace(0.5, 1.0, 1200)).astype(np.uint8)
    cleaned, applied = cleanup.clean(shaded, cleanup.CleanupOptions(threshold=True))
    assert applied == ["threshold"]
    assert set(np.unique(cleaned)) <= {0, 255}


def test_perspective_flattens_a_photographed_page():
    page = cv2.cvtColor(staff_page(), cv2.COLOR_GRAY2BGR)
    height, width = page.shape[:2]
    source = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    target = np.float32([[260, 180], [1380, 120], [1500, 1050], [140, 980]])
    photo = cv2.warpPerspective(
        page, cv2.getPerspectiveTransform(source, target), (1600, 1200), borderValue=(40, 40, 40)
    )

    corners = cleanup.find_page_corners(photo)
    assert corners is not None
    assert np.allclose(corners, target, atol=12)

    cleaned, applied = cleanup.clean(photo, cleanup.CleanupOptions(perspective=True, deskew=True))
    assert "perspective" in applied
    assert abs(cleanup.estimate_skew(cleaned)) < 0.5
    assert cleaned.mean() > 200  # the dark table is gone


def test_perspective_ignores_a_full_frame_scan():
    page = cv2.cvtColor(staff_page(), cv2.COLOR_GRAY2BGR)
    assert cleanup.find_page_corners(page) is None


# --- omr helpers -------------------------------------------------------------


def test_read_musicxml_from_mxl_uses_the_container(tmp_path, simple_xml):
    mxl = tmp_path / "score.mxl"
    with zipfile.ZipFile(mxl, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container><rootfiles>'
            '<rootfile full-path="inner/score.xml"/></rootfiles></container>',
        )
        archive.writestr("decoy.xml", "<nope/>")
        archive.write(simple_xml, "inner/score.xml")
    assert read_musicxml(mxl) == simple_xml.read_bytes()


def test_read_musicxml_from_mxl_without_container(tmp_path, simple_xml):
    mxl = tmp_path / "score.mxl"
    with zipfile.ZipFile(mxl, "w") as archive:
        archive.write(simple_xml, "score.musicxml")
    assert read_musicxml(mxl) == simple_xml.read_bytes()


def test_natural_key_orders_pages_numerically(tmp_path):
    names = ["page-10.mxl", "page-2.mxl", "page-1.mvt2.mxl", "page-1.mvt1.mxl"]
    ordered = sorted((tmp_path / name for name in names), key=natural_key)
    assert [p.name for p in ordered] == ["page-1.mvt1.mxl", "page-1.mvt2.mxl", "page-2.mxl", "page-10.mxl"]


def test_merge_appends_pages_and_renumbers_measures(tmp_path):
    first = write_xml(make_score([[n("G4", length=4.0)], [n("A4", length=4.0)]]), tmp_path / "1.musicxml")
    second = write_xml(make_score([[n("B4", length=4.0)]]), tmp_path / "2.musicxml")

    merged = converter.parse(merge_musicxml([first, second], tmp_path / "merged.musicxml"))
    measures = merged.parts[0].getElementsByClass("Measure")
    assert [m.number for m in measures] == [1, 2, 3]
    assert [p.nameWithOctave for p in merged.pitches] == ["G4", "A4", "B4"]
