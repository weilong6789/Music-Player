import os
import shutil
from pathlib import Path

from app import config
from app.pipeline.merge import merge_musicxml
from app.pipeline.omr.base import OMRError
from app.pipeline.omr.util import natural_key, read_musicxml, run_command


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
        binary = self.binary()
        if binary is None:
            raise OMRError("Audiveris isn't installed")

        work = out_dir / "audiveris-work"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        try:
            cmd = [str(binary), "-batch", "-export", "-output", str(work), "--"]
            cmd += [str(path.resolve()) for path in image_paths]
            run_command(cmd, cwd=work, label="Audiveris")

            # One file per page, or per movement within a page, depending on the version.
            exports = sorted(
                (p for ext in ("*.mxl", "*.musicxml", "*.xml") for p in work.rglob(ext)),
                key=lambda p: (natural_key(p.parent), natural_key(p)),
            )
            if not exports:
                raise OMRError("Audiveris finished without exporting a score")

            plain: list[Path] = []
            for index, export in enumerate(exports, start=1):
                target = work / f"export-{index}.musicxml"
                target.write_bytes(read_musicxml(export))
                plain.append(target)

            dest = out_dir / f"{self.name}.musicxml"
            if len(plain) == 1:
                shutil.copyfile(plain[0], dest)
            else:
                merge_musicxml(plain, dest)
            return dest
        finally:
            shutil.rmtree(work, ignore_errors=True)


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)
