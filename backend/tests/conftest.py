from pathlib import Path

import pytest
from music21 import clef, meter, note, stream

from app import config


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Keep every test away from the real data folder."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "EXCERPTS_DIR", tmp_path / "data" / "excerpts")
    return tmp_path / "data"


def make_score(measures: list[list], part_name: str | None = "Violin", extras=()) -> stream.Score:
    """A one-part 4/4 score. `extras` are inserted at the start of the first measure."""
    part = stream.Part()
    if part_name:
        part.partName = part_name
    for number, contents in enumerate(measures, start=1):
        measure = stream.Measure(number=number)
        if number == 1:
            measure.insert(0, clef.TrebleClef())
            measure.insert(0, meter.TimeSignature("4/4"))
            for extra in extras:
                measure.insert(0, extra)
        for element in contents:
            measure.append(element)
        part.append(measure)
    score = stream.Score()
    score.insert(0, part)
    return score


def n(name: str, printed: bool | None = None, tie: str | None = None, length: float = 1.0) -> note.Note:
    """A note; `printed` says whether its accidental is drawn in the score."""
    from music21 import tie as tie_module

    result = note.Note(name, quarterLength=length)
    if result.pitch.accidental is not None:
        result.pitch.accidental.displayStatus = True if printed is None else printed
    if tie:
        result.tie = tie_module.Tie(tie)
    return result


def write_xml(score: stream.Score, path: Path) -> Path:
    score.write("musicxml", fp=path, makeNotation=False)
    return path


@pytest.fixture
def simple_xml(tmp_path) -> Path:
    from music21 import tempo

    score = make_score(
        [[n("G4"), n("A4"), n("B4"), n("C5")], [n("D5", length=4.0)]],
        extras=[tempo.MetronomeMark(number=72)],
    )
    return write_xml(score, tmp_path / "simple.musicxml")
