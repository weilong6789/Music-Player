import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from app.pipeline.omr.base import OMRError

OMR_TIMEOUT_SECONDS = 900


def run_command(cmd: list[str], cwd: Path, label: str) -> None:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=OMR_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as err:
        raise OMRError(f"{label} took longer than {OMR_TIMEOUT_SECONDS // 60} minutes") from err
    except OSError as err:
        raise OMRError(f"{label} couldn't be started: {err}") from err
    if result.returncode != 0:
        tail = "\n".join((result.stderr or result.stdout).strip().splitlines()[-8:])
        raise OMRError(f"{label} exited with code {result.returncode}:\n{tail}")


def read_musicxml(path: Path) -> bytes:
    """MusicXML bytes from a .musicxml/.xml file or a compressed .mxl."""
    if path.suffix.lower() != ".mxl":
        return path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        root_file = None
        if "META-INF/container.xml" in names:
            container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
            for element in container.iter():
                if element.tag.rsplit("}", 1)[-1] == "rootfile" and element.get("full-path"):
                    root_file = element.get("full-path")
                    break
        if root_file is None:
            candidates = [
                n for n in names
                if not n.startswith("META-INF/") and n.lower().endswith((".xml", ".musicxml"))
            ]
            if not candidates:
                raise OMRError(f"{path.name} has no MusicXML inside")
            root_file = candidates[0]
        return archive.read(root_file)


def natural_key(path: Path) -> list:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path.name)]
