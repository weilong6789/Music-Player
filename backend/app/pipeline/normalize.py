"""music21 processing of the raw OMR MusicXML: parts, tempo, accidental rule."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from music21 import chord, converter, duration, expressions, key, note, pitch, stream, tempo

DEFAULT_BPM = 80.0
ACCIDENTAL_RULES = ("bar", "note")

_VIOLIN = re.compile(r"violin|violon(?!c)|\bvln?\b|\bvl\.|geige", re.IGNORECASE)

# "♩ = 72", "q=72", "Allegro (♩.=132)". The note symbol is optional because OMR often drops it.
_BEAT_UNITS = {
    "♩": 1.0, "\U0001d15f": 1.0, "q": 1.0,
    "♪": 0.5, "\U0001d160": 0.5, "e": 0.5,
    "\U0001d15e": 2.0, "h": 2.0,
}
_TEMPO_TEXT = re.compile(
    r"(?:(?P<unit>[♩♪\U0001d15e\U0001d15f\U0001d160]|(?<![A-Za-z])[qeh])\s*(?P<dot>[.\U0001d16d])?)?"
    r"\s*=\s*(?:c(?:irc)?a?\.?\s*)?(?P<bpm>\d{2,3})(?!\d)"
)


class EmptyScoreError(ValueError):
    """The MusicXML has no notes."""


@dataclass
class NormalizeResult:
    tempo_bpm: float
    tempo_beat: float  # length of the beat the BPM counts, in quarter notes
    tempo_source: str  # "marking" | "text" | "default"
    parts: list[dict]
    playback_part: int
    measure_count: int
    note_count: int
    warnings: list[str] = field(default_factory=list)


def normalize(src: Path, dest: Path, accidental_rule: str = "bar") -> NormalizeResult:
    if accidental_rule not in ACCIDENTAL_RULES:
        raise ValueError(f"Unknown accidental rule: {accidental_rule}")

    score = converter.parse(src, format="musicxml")
    if not isinstance(score, stream.Score) or not score.parts:
        raise EmptyScoreError("No parts found in the recognized score")

    note_count = sum(1 for _ in score.recurse().getElementsByClass((note.Note, chord.Chord)))
    if note_count == 0:
        raise EmptyScoreError("No notes found in the recognized score")

    warnings: list[str] = []
    parts, playback_part = describe_parts(score)

    bpm, beat, source = detect_tempo(score)
    if source == "text":
        # The printed marking wasn't recognized as one. Add it so renderers and playback see it.
        first_measure = score.parts[playback_part].getElementsByClass(stream.Measure).first()
        if first_measure is not None:
            mark = tempo.MetronomeMark(number=bpm, referent=duration.Duration(beat))
            first_measure.insert(0, mark)

    if accidental_rule == "note":
        if not apply_note_accidental_rule(score):
            warnings.append(
                "The OMR output doesn't say which accidentals are printed, "
                "so the per-note accidental rule wasn't applied."
            )

    dest.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=dest, makeNotation=False)

    measure_count = max(len(p.getElementsByClass(stream.Measure)) for p in score.parts)
    return NormalizeResult(bpm, beat, source, parts, playback_part, measure_count, note_count, warnings)


def describe_parts(score: stream.Score) -> tuple[list[dict], int]:
    parts: list[dict] = []
    playback = None
    for index, part in enumerate(score.parts):
        instrument = part.getInstrument(returnDefault=False)
        names = [part.partName, getattr(instrument, "instrumentName", None), getattr(instrument, "partName", None)]
        name = next((n for n in names if n), None) or f"Part {index + 1}"
        parts.append({"index": index, "name": name})
        if playback is None and any(n and _VIOLIN.search(n) for n in names):
            playback = index
    return parts, playback if playback is not None else 0


def detect_tempo(score: stream.Score) -> tuple[float, float, str]:
    """(bpm, beat length in quarter notes, source)."""
    marks = list(score.recurse().getElementsByClass(tempo.MetronomeMark))
    for mark in marks:
        if mark.number is not None and not mark.numberImplicit:
            return float(mark.number), float(mark.referent.quarterLength), "marking"
    for mark in marks:
        # <sound tempo="..."> with no printed metronome mark; always quarter notes per minute.
        if mark.numberSounding is not None:
            return float(mark.numberSounding), 1.0, "marking"

    for text in _score_texts(score):
        found = parse_tempo_text(text)
        if found:
            return found[0], found[1], "text"

    return DEFAULT_BPM, 1.0, "default"


def parse_tempo_text(text: str) -> tuple[float, float] | None:
    for match in _TEMPO_TEXT.finditer(text):
        bpm = float(match["bpm"])
        if not 20 <= bpm <= 400:
            continue
        beat = _BEAT_UNITS.get(match["unit"] or "", 1.0)
        if match["dot"] and match["unit"]:
            beat *= 1.5
        return bpm, beat
    return None


def _score_texts(score: stream.Score):
    for element in score.recurse():
        if isinstance(element, expressions.TextExpression):
            yield element.content or ""
        elif isinstance(element, tempo.TempoText):
            yield element.text or ""
        elif isinstance(element, tempo.MetronomeMark) and element.text:
            yield str(element.text)


def apply_note_accidental_rule(score: stream.Score) -> bool:
    """Make an accidental apply only to the note it's printed on.

    OMR output follows the traditional rule: a sharp carries through the bar, so later notes
    on the same line get the alteration without a printed sign. Here every note without a
    printed accidental goes back to what the key signature says. Notes tied from a previous
    note keep that note's pitch.

    Returns False without touching anything when the score has alterations but no printed
    accidentals at all, since then there's no way to tell printed from carried ones.
    """
    pitched = [
        n
        for element in score.recurse().getElementsByClass((note.Note, chord.Chord))
        for n in ([element] if isinstance(element, note.Note) else element.notes)
    ]
    has_alter = any(n.pitch.accidental is not None and n.pitch.alter != 0 for n in pitched)
    has_printed = any(_is_printed(n.pitch.accidental) for n in pitched)
    if has_alter and not has_printed:
        return False

    for part in score.parts:
        key_alters: dict[str, float] = {}
        tied: dict[tuple[str, int | None], float] = {}
        for element in part.recurse():
            if isinstance(element, key.KeySignature):
                key_alters = {p.step: p.alter for p in element.alteredPitches}
                continue
            if isinstance(element, note.Note):
                notes = [element]
            elif isinstance(element, chord.Chord):
                notes = list(element.notes)
            else:
                continue
            for n in notes:
                where = (n.pitch.step, n.pitch.octave)
                tied_in = n.tie is not None and n.tie.type in ("stop", "continue")
                if tied_in and where in tied:
                    _set_alter(n.pitch, tied[where])
                elif not _is_printed(n.pitch.accidental):
                    _set_alter(n.pitch, key_alters.get(n.pitch.step, 0.0))
                if n.tie is not None and n.tie.type in ("start", "continue"):
                    tied[where] = n.pitch.alter
                else:
                    tied.pop(where, None)
    return True


def _is_printed(accidental: pitch.Accidental | None) -> bool:
    return accidental is not None and accidental.displayStatus is True


def _set_alter(p: pitch.Pitch, alter: float) -> None:
    if p.alter == alter:
        return
    if alter == 0:
        p.accidental = None
    else:
        accidental = pitch.Accidental(alter)
        accidental.displayStatus = False
        p.accidental = accidental
