# Excerpt Player

Local Mac app that reads a scanned or photographed violin excerpt and plays it back. Spec is in `BUILD_PLAN.md`, background in `BRAINSTORM.md`.

Status: milestones 1 and 2. You can upload a PDF, PNG or JPG, the app reads it into MusicXML and keeps it in a library. Rendering the score and playback come in milestone 3.

## Install

```bash
brew install uv node
```

Install Audiveris from its GitHub releases page (the macOS `.dmg`). On first launch macOS may need it allowed under System Settings → Privacy & Security. If it lives somewhere other than `/Applications/Audiveris.app`, set `AUDIVERIS_BIN` to the binary path.

```bash
make setup
```

`make setup` also downloads homr's recognition models (about 130 MB), the one step that needs a connection.

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
