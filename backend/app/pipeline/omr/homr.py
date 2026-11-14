import importlib.util
import shutil
import sys
from pathlib import Path

from app.pipeline.omr.base import OMRError
from app.pipeline.omr.util import run_command


class HomrEngine:
    name = "homr"

    def available(self) -> bool:
        return importlib.util.find_spec("homr") is not None

    def detail(self) -> str:
        if self.available():
            return "Python package"
        return "Not installed. Run `make setup`."

    def run(self, image_paths: list[Path], out_dir: Path) -> Path:
        if not self.available():
            raise OMRError("homr isn't installed")

        # homr writes its output next to the input, so give it copies in a scratch folder.
        work = out_dir / "homr-work"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        try:
            copies = []
            for index, path in enumerate(image_paths, start=1):
                copy = work / f"page-{index}{path.suffix}"
                shutil.copyfile(path, copy)
                copies.append(copy)

            # Several images in one call are merged by homr into one score named after the first.
            cmd = [sys.executable, "-m", "homr.main", "--no-title", *[str(c) for c in copies]]
            run_command(cmd, cwd=work, label="homr")

            produced = copies[0].with_suffix(".musicxml")
            if not produced.is_file():
                raise OMRError("homr finished without writing a score")
            dest = out_dir / f"{self.name}.musicxml"
            shutil.move(produced, dest)
            return dest
        finally:
            shutil.rmtree(work, ignore_errors=True)
