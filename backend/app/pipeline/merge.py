"""Join the MusicXML of several pages (or movements) into one score."""

from pathlib import Path

from music21 import converter, stream


def merge_musicxml(paths: list[Path], dest: Path) -> Path:
    base = converter.parse(paths[0], format="musicxml")
    base_parts = list(base.parts)
    for path in paths[1:]:
        following = converter.parse(path, format="musicxml")
        for index, part in enumerate(following.parts):
            if index >= len(base_parts):
                break
            target = base_parts[index]
            existing = list(target.getElementsByClass(stream.Measure))
            next_number = (existing[-1].number or len(existing)) + 1 if existing else 1
            for measure in list(part.getElementsByClass(stream.Measure)):
                part.remove(measure)
                measure.number = next_number
                next_number += 1
                target.append(measure)
    base.write("musicxml", fp=dest, makeNotation=False)
    return dest
