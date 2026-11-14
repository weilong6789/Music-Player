from pathlib import Path
from typing import Protocol


class OMREngine(Protocol):
    name: str

    def available(self) -> bool: ...

    def detail(self) -> str:
        """Where the engine was found, or how to install it."""
        ...

    def run(self, image_paths: list[Path], out_dir: Path) -> Path:
        """Run OMR and return the path of the MusicXML output."""
        ...
