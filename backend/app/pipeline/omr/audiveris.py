import os
import shutil
from pathlib import Path

from app import config


class AudiverisEngine:
    name = "audiveris"

    def binary(self) -> Path | None:
        override = os.environ.get(config.AUDIVERIS_ENV_VAR)
        if override:
            path = Path(override).expanduser()
            return path if _is_executable(path) else None
        if _is_executable(config.AUDIVERIS_DEFAULT_BIN):
            return config.AUDIVERIS_DEFAULT_BIN
        for name in ("Audiveris", "audiveris"):
            found = shutil.which(name)
            if found:
                return Path(found)
        return None

    def available(self) -> bool:
        return self.binary() is not None

    def detail(self) -> str:
        binary = self.binary()
        if binary:
            return str(binary)
        override = os.environ.get(config.AUDIVERIS_ENV_VAR)
        if override:
            return f"{config.AUDIVERIS_ENV_VAR}={override} is not an executable file"
        return (
            "Not found. Install the macOS .dmg from the Audiveris GitHub releases page, "
            f"or set {config.AUDIVERIS_ENV_VAR} to the binary."
        )

    def run(self, image_paths: list[Path], out_dir: Path) -> Path:
        raise NotImplementedError("Audiveris OMR arrives in milestone 2")


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)
