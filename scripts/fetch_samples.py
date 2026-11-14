"""Download the VSCO 2 Community Edition solo violin sustain samples (CC0).

Writes data/samples/violin/<note>.wav and an index.json mapping note name → file,
which the app hands to Tone.Sampler. The sampler pitch-shifts between the sampled notes.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

BASE = "https://raw.githubusercontent.com/sgossner/VSCO-2-CE/master/Strings/Solo Violin/Arco Vib/"
NOTES = ["G3", "A3", "C4", "E4", "G4", "A4", "C5", "E5", "G5", "A5", "C6", "E6", "G6", "A6", "C7"]

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("EXCERPT_DATA_DIR", ROOT / "data")).expanduser()
DEST = DATA_DIR / "samples" / "violin"


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=60) as response, tmp.open("wb") as out:
        while chunk := response.read(1 << 16):
            out.write(chunk)
    if tmp.stat().st_size < 1024:
        tmp.unlink()
        raise OSError("the downloaded file is empty")
    tmp.replace(dest)


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    index: dict[str, str] = {}
    failed: list[str] = []
    for note in NOTES:
        name = f"{note}.wav"
        target = DEST / name
        if not target.is_file():
            url = quote(f"{BASE}LLVln_ArcoVib_{note}_f.wav", safe=":/")
            try:
                download(url, target)
                print(f"violin {note}: downloaded")
            except (urllib.error.URLError, OSError) as err:
                failed.append(note)
                print(f"violin {note}: failed ({err})", file=sys.stderr)
                continue
        index[note] = name

    if index:
        (DEST / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    if failed:
        print(
            f"{len(failed)} of {len(NOTES)} samples are missing. "
            "The app plays a pure tone until they're there; run `make setup` again to retry.",
            file=sys.stderr,
        )
        return 1
    print(f"{len(index)} violin samples in {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
