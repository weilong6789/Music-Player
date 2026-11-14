# Excerpt Player

Local Mac app that reads a scanned or photographed violin excerpt and plays it back. Spec is in `BUILD_PLAN.md`, background in `BRAINSTORM.md`.

Status: milestones 1 to 3. Upload a PDF, PNG or JPG, the app reads it into MusicXML, shows the result next to the original and plays it back with a violin sound at an adjustable tempo. Looping, step mode and note correction come in later milestones.

## Install

```bash
brew install uv node
```

Install Audiveris from its GitHub releases page (the macOS `.dmg`). On first launch macOS may need it allowed under System Settings → Privacy & Security. If it lives somewhere other than `/Applications/Audiveris.app`, set `AUDIVERIS_BIN` to the binary path.

```bash
make setup
```

`make setup` also downloads homr's recognition models (about 130 MB) and the violin samples (about 35 MB). After that the app works offline.

## Run

```bash
make start
```

Builds the frontend, starts the server and opens `http://localhost:8000`.

## Develop

```bash
make dev
```

Backend with reload on `:8000`, Vite dev server on `http://localhost:5173` proxying `/api`.

```bash
make test
```

## How an upload is processed

1. PDFs are rendered to PNG pages at 300 DPI. Images are used as they are, with the EXIF rotation applied.
2. Optional cleanup. PDFs get none by default. Images get perspective correction (when a page outline is found) and deskew. A black-and-white threshold is available but off. All three are checkboxes on the upload form.
3. OMR. "Auto" uses Audiveris for PDFs and homr for images, and falls back to the other engine if the first one fails or finds no notes.
4. The result is normalized with music21: the violin part (or the first part) is marked for playback, the tempo marking is looked up, and the accidental rule is applied.

Each excerpt lives in `data/excerpts/<id>/` with the original file, the page images, the raw OMR output and `score.musicxml`. Set `EXCERPT_DATA_DIR` to keep the data somewhere else.

### Accidental rule

"Apply only to their own note" is for contemporary scores where a sharp doesn't carry through the bar. It needs the OMR output to say which accidentals are printed. homr 0.7 doesn't record that, so with homr the rule is skipped and the excerpt shows a warning.

### Tempo

If no metronome mark or "♩ = 72" style text is found, the excerpt gets 80 BPM as a placeholder and is flagged so the tempo can be entered by hand once the player exists. homr doesn't read tempo markings.

## Playback

The score is drawn with Verovio and played with Tone.js. The tempo field starts at the marking found in the score and can be overwritten; the change is saved with the excerpt. The speed slider goes from 25% to 150% of that tempo and can be moved while playing. Space toggles play and pause.

For a score with several parts, only the violin part (or the first part) is played.

### Violin sound

The samples are the solo violin sustains from [VSCO 2 Community Edition](https://github.com/sgossner/VSCO-2-CE) by Versilian Studios (CC0). They're recordings of a real player with vibrato, so individual notes sit up to about 12 cents off equal temperament. If the samples are missing, playback uses a plain synthesized tone, which is exactly in tune; run `make setup` again to fetch them.
