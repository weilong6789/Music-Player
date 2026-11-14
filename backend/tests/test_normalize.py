import pytest
from music21 import chord, converter, expressions, key, note, stream, tempo

from app.pipeline.normalize import EmptyScoreError, detect_tempo, normalize, parse_tempo_text
from conftest import make_score, n, write_xml


def pitches(path) -> list[str]:
    score = converter.parse(path, format="musicxml")
    names = []
    for element in score.recurse().getElementsByClass((note.Note, chord.Chord)):
        names += [p.nameWithOctave for p in element.pitches]
    return names


def run(score, tmp_path, rule="bar"):
    out = tmp_path / "score.musicxml"
    result = normalize(write_xml(score, tmp_path / "raw.musicxml"), out, rule)
    return result, out


# --- tempo ---------------------------------------------------------------


def test_tempo_from_metronome_mark(tmp_path):
    score = make_score([[n("G4", length=4.0)]], extras=[tempo.MetronomeMark(number=72)])
    result, _ = run(score, tmp_path)
    assert (result.tempo_bpm, result.tempo_beat, result.tempo_source) == (72, 1.0, "marking")


def test_tempo_from_dotted_quarter_mark(tmp_path):
    from music21 import duration

    mark = tempo.MetronomeMark(number=56, referent=duration.Duration(1.5))
    result, _ = run(make_score([[n("G4", length=4.0)]], extras=[mark]), tmp_path)
    assert (result.tempo_bpm, result.tempo_beat, result.tempo_source) == (56, 1.5, "marking")


def test_tempo_from_text_expression_is_added_to_the_score(tmp_path):
    text = expressions.TextExpression("Allegro (♩=132)")
    result, out = run(make_score([[n("G4", length=4.0)]], extras=[text]), tmp_path)
    assert (result.tempo_bpm, result.tempo_beat, result.tempo_source) == (132, 1.0, "text")

    marks = list(converter.parse(out).recurse().getElementsByClass(tempo.MetronomeMark))
    assert [m.number for m in marks] == [132]


def test_tempo_word_alone_falls_back_to_default():
    # "Allegro" makes music21 guess a number; that's not a printed tempo.
    score = make_score([[n("G4", length=4.0)]], extras=[tempo.MetronomeMark("Allegro")])
    assert detect_tempo(score) == (80, 1.0, "default")


def test_tempo_default(tmp_path):
    result, _ = run(make_score([[n("G4", length=4.0)]]), tmp_path)
    assert (result.tempo_bpm, result.tempo_beat, result.tempo_source) == (80, 1.0, "default")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("♩ = 72", (72, 1.0)),
        ("q=72", (72, 1.0)),
        ("Allegro (♩=132)", (132, 1.0)),
        ("♪ = 180", (180, 0.5)),
        ("♩. = 60", (60, 1.5)),
        ("h = 54", (54, 2.0)),
        ("= 96", (96, 1.0)),
        ("♩ = ca. 66", (66, 1.0)),
        ("Tempo I", None),
        ("sul pont.", None),
        ("♩ = 5", None),
        ("the = 100", (100, 1.0)),  # the "e" belongs to a word, so it isn't an eighth note
    ],
)
def test_parse_tempo_text(text, expected):
    assert parse_tempo_text(text) == expected


# --- accidental rule -----------------------------------------------------


def carried_sharp_score():
    # F#, then two Fs that only sound sharp because of the bar rule, then a new bar.
    return make_score(
        [
            [n("F#4", printed=True), n("F#4", printed=False), n("G4"), n("F#4", printed=False)],
            [n("F4"), n("B-4", printed=True), n("B-4", printed=False), n("B-5", printed=True)],
        ]
    )


def test_bar_rule_keeps_carried_accidentals(tmp_path):
    _, out = run(carried_sharp_score(), tmp_path, "bar")
    assert pitches(out) == ["F#4", "F#4", "G4", "F#4", "F4", "B-4", "B-4", "B-5"]


def test_note_rule_resets_carried_accidentals(tmp_path):
    result, out = run(carried_sharp_score(), tmp_path, "note")
    assert pitches(out) == ["F#4", "F4", "G4", "F4", "F4", "B-4", "B4", "B-5"]
    assert result.warnings == []


def test_note_rule_keeps_key_signature(tmp_path):
    score = make_score(
        [[n("F#4", printed=False), n("F4"), n("F#4", printed=False), n("C#5", printed=False)]],
        extras=[key.KeySignature(2)],
    )
    # The printed natural is written as an explicit accidental.
    natural = score.recurse().notes[1]
    from music21 import pitch

    natural.pitch.accidental = pitch.Accidental("natural")
    natural.pitch.accidental.displayStatus = True

    _, out = run(score, tmp_path, "note")
    assert pitches(out) == ["F#4", "F4", "F#4", "C#5"]


def test_note_rule_keeps_pitch_across_ties(tmp_path):
    score = make_score(
        [
            [n("G4", length=3.0), n("C#5", printed=True, tie="start")],
            [n("C#5", printed=False, tie="stop"), n("C#5", printed=False), n("D5", length=2.0)],
        ]
    )
    _, out = run(score, tmp_path, "note")
    assert pitches(out) == ["G4", "C#5", "C#5", "C5", "D5"]


def test_note_rule_applies_inside_chords(tmp_path):
    first = chord.Chord(["E-4", "G4"])
    first.pitches[0].accidental.displayStatus = True
    second = chord.Chord(["E-4", "A4"])
    second.pitches[0].accidental.displayStatus = False
    first.quarterLength = second.quarterLength = 2.0

    _, out = run(make_score([[first, second]]), tmp_path, "note")
    assert pitches(out) == ["E-4", "G4", "E4", "A4"]


def test_note_rule_skipped_when_no_accidental_is_marked_printed(tmp_path):
    score = make_score([[n("F#4", printed=False), n("F#4", printed=False), n("G4", length=2.0)]])
    result, out = run(score, tmp_path, "note")
    assert pitches(out) == ["F#4", "F#4", "G4"]
    assert len(result.warnings) == 1


# --- parts and structure --------------------------------------------------


def test_violin_part_is_the_playback_default(tmp_path):
    score = make_score([[n("C3", length=4.0)]], part_name="Violoncello")
    violin = make_score([[n("G4", length=4.0)]], part_name="Violin I").parts[0]
    score.insert(0, violin)

    result, _ = run(score, tmp_path)
    assert [p["name"] for p in result.parts] == ["Violoncello", "Violin I"]
    assert result.playback_part == 1


def test_first_part_is_the_default_without_a_violin(tmp_path):
    result, _ = run(make_score([[n("C4", length=4.0)]], part_name=None), tmp_path)
    assert result.parts == [{"index": 0, "name": "Part 1"}]
    assert result.playback_part == 0


def test_counts(simple_xml, tmp_path):
    result = normalize(simple_xml, tmp_path / "out.musicxml")
    assert (result.measure_count, result.note_count) == (2, 5)


def test_empty_score_is_rejected(tmp_path):
    score = make_score([[note.Rest(quarterLength=4.0)]])
    with pytest.raises(EmptyScoreError):
        run(score, tmp_path)
    assert isinstance(score, stream.Score)
