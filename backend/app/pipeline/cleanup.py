"""OpenCV preprocessing. Every step is optional because cleanup can make clean scans worse."""

from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

MAX_SKEW_DEGREES = 15.0
MIN_SKEW_DEGREES = 0.1


@dataclass(frozen=True)
class CleanupOptions:
    perspective: bool = False
    deskew: bool = False
    threshold: bool = False

    @property
    def any(self) -> bool:
        return self.perspective or self.deskew or self.threshold

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


def load_image(path: Path) -> np.ndarray:
    """Read an image as BGR. OpenCV applies the EXIF rotation itself."""
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Can't read {path.name} as an image")
    return image


def clean(image: np.ndarray, options: CleanupOptions) -> tuple[np.ndarray, list[str]]:
    """Returns the processed image and the steps that actually changed it."""
    applied: list[str] = []
    if not options.any:
        return image, applied

    if options.perspective:
        warped = correct_perspective(image)
        if warped is not None:
            image = warped
            applied.append("perspective")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    if options.deskew:
        angle = estimate_skew(gray)
        if MIN_SKEW_DEGREES <= abs(angle) <= MAX_SKEW_DEGREES:
            gray = rotate(gray, angle)
            applied.append("deskew")

    if options.threshold:
        gray = adaptive_threshold(gray)
        applied.append("threshold")

    return gray, applied


def estimate_skew(gray: np.ndarray) -> float:
    """Angle of the staff lines in degrees. Positive means the lines fall to the right."""
    height, width = gray.shape[:2]
    scale = min(1.0, 1600 / max(height, width))
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray
    edges = cv2.Canny(small, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 1800,
        threshold=100,
        minLineLength=small.shape[1] // 4,
        maxLineGap=small.shape[1] // 50,
    )
    if lines is None:
        return 0.0

    angles: list[float] = []
    weights: list[float] = []
    for x1, y1, x2, y2 in lines[:, 0]:
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if abs(angle) <= MAX_SKEW_DEGREES:
            angles.append(angle)
            weights.append(float(np.hypot(x2 - x1, y2 - y1)))
    if not angles:
        return 0.0

    order = np.argsort(angles)
    cumulative = np.cumsum(np.array(weights)[order])
    median_index = int(np.searchsorted(cumulative, cumulative[-1] / 2))
    return float(np.array(angles)[order][median_index])


def rotate(image: np.ndarray, angle: float) -> np.ndarray:
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def adaptive_threshold(gray: np.ndarray) -> np.ndarray:
    block = max(15, (min(gray.shape[:2]) // 40) | 1)
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 15
    )


def correct_perspective(image: np.ndarray) -> np.ndarray | None:
    """Flatten a photographed page. Returns None unless a clear page outline is found."""
    corners = find_page_corners(image)
    if corners is None:
        return None
    tl, tr, br, bl = corners
    width = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    height = int(round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))))
    if width < 100 or height < 100:
        return None
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(corners.astype(np.float32), target)
    return cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_CUBIC)


def find_page_corners(image: np.ndarray) -> np.ndarray | None:
    """Corners (tl, tr, br, bl) of a bright page on a darker background, in image pixels."""
    height, width = image.shape[:2]
    scale = min(1.0, 1000 / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if small.ndim == 3 else small
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    image_area = small.shape[0] * small.shape[1]
    area = cv2.contourArea(contour)
    # A page that already fills the frame (a scan) has nothing to correct.
    if not 0.3 * image_area <= area <= 0.92 * image_area:
        return None

    approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
    if len(approx) != 4 or not cv2.isContourConvex(approx):
        return None

    points = approx.reshape(4, 2).astype(np.float64) / scale
    sums = points.sum(axis=1)
    diffs = points[:, 0] - points[:, 1]
    ordered = np.array(
        [points[np.argmin(sums)], points[np.argmax(diffs)], points[np.argmax(sums)], points[np.argmin(diffs)]]
    )
    if len({tuple(p) for p in ordered}) != 4:
        return None
    return ordered
