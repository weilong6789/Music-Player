import importlib.util
import shutil
from pathlib import Path


class HomrEngine:
    name = "homr"

    def available(self) -> bool:
        return shutil.which("homr") is not None or importlib.util.find_spec("homr") is not None

    def detail(self) -> str:
        cli = shutil.which("homr")
        if cli:
            return cli
        if importlib.util.find_spec("homr") is not None:
            return "Python package"
        return "Not installed. It gets added to the project dependencies with the import pipeline."

    def run(self, image_paths: list[Path], out_dir: Path) -> Path:
        raise NotImplementedError("homr OMR arrives in milestone 2")
