"""Paths and settings. Everything can be overridden with env vars."""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.environ.get("EXCERPT_DATA_DIR", ROOT_DIR / "data")).expanduser()
EXCERPTS_DIR = DATA_DIR / "excerpts"
SAMPLES_DIR = DATA_DIR / "samples"

FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

AUDIVERIS_DEFAULT_BIN = Path("/Applications/Audiveris.app/Contents/MacOS/Audiveris")
AUDIVERIS_ENV_VAR = "AUDIVERIS_BIN"
