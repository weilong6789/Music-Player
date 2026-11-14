# Build Plan: Excerpt Player

Implementation spec for building the app. Background and the options considered are in `BRAINSTORM.md`. This file has the decisions.

## What it does

A local app for macOS. Upload a scanned or photographed violin audition excerpt (PDF/PNG/JPG). The app reads the music with OMR and shows the rendered score next to the original image. The user fixes recognition errors, then plays the excerpt back with a violin sound, adjustable tempo, and measure-range looping.

The main use case is contemporary pieces with no recordings and heavy dissonance, where the user can't tell by ear whether they're reading it right. Accurate pitch matters more than a realistic sound.

## Constraints

- Runs locally on a Mac (Apple Silicon and Intel). Nothing hosted, no accounts, no paid services.
- Works offline once installed.
- Free and open source dependencies only.
- Python backend, browser UI at `http://localhost:8000`.
- One command to start.
- Single user, no auth.

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Python env | **uv**, Python 3.12 | `uv sync` installs everything |
| Web server | **FastAPI** + uvicorn | Serves API and the built frontend |
| PDF → images | **PyMuPDF** (`pymupdf`) | No poppler system dependency |
| Image cleanup | **OpenCV** (`opencv-python-headless`) | Deskew, perspective fix, threshold |
| OMR engine 1 | **Audiveris** (CLI) | Installed separately from its macOS release. Best on clean PDFs. |
| OMR engine 2 | **homr** (pip) | Better on phone photos |
| Score processing | **music21** | Parse/normalize MusicXML, find tempo marking, accidental rule |
| Frontend build | **Vite + TypeScript**, no framework | Vanilla TS keeps it small. Built output served by FastAPI. |
| Score rendering | **Verovio** (npm `verovio`, WASM) | Renders SVG, gives a timemap and MEI with stable element IDs |
| Audio | **Tone.js** | Scheduling, `Tone.Sampler` for violin, synth for pure tone |
| Violin samples | **VSCO 2 Community Edition** (CC0) | Downloaded by a setup script, not committed |

## Architecture

```
Browser (Vite/TS)                          FastAPI (Python)
─────────────────                          ────────────────
upload form  ──── POST /api/excerpts ───►  save original
                                           PDF → page PNGs (PyMuPDF)
                                           cleanup (OpenCV)
                                           OMR (Audiveris or homr) → MusicXML
                                           normalize (music21)
             ◄─── excerpt id + metadata ──
Verovio loads MusicXML
  → exports MEI (canonical working copy)
  ──── PUT /api/excerpts/{id}/score ───►  save score.mei
note edits change MEI DOM by xml:id
  ──── PUT (debounced) ────────────────►  save score.mei
Verovio timemap → Tone.js playback
```

**MEI is the editable working copy.** After the first load, the frontend asks Verovio for MEI (`toolkit.getMEI()`) and saves it. Every MEI element has a stable `xml:id`, so edits are DOM changes on `<note>` attributes (`pname`, `oct`, `accid`, `dur`, `dots`), followed by a re-render. This avoids mapping note identities between music21 and Verovio. The original OMR MusicXML is kept untouched so the user can reset to it.

**Playback timing comes from Verovio's timemap** (`toolkit.renderToTimemap()`), which gives note-on/off element IDs with millisecond timestamps (`tstamp`) at the score's own tempos, including tempo changes. Tempo control scales these times by a percentage. Pitch per note comes from `toolkit.getMIDIValuesForElement(id)`, or from the MEI attributes directly.

## Project layout

```
.
├── pyproject.toml
├── Makefile                 # setup, dev, start, test
├── README.md                # Mac install + usage
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, static mount
│   │   ├── config.py        # paths, Audiveris binary location, data dir
│   │   ├── api/excerpts.py
│   │   ├── pipeline/
│   │   │   ├── pdf.py       # PDF → PNG pages
│   │   │   ├── cleanup.py   # OpenCV preprocessing
│   │   │   ├── omr/
│   │   │   │   ├── base.py      # OMREngine interface
│   │   │   │   ├── audiveris.py
│   │   │   │   └── homr.py
│   │   │   └── normalize.py # music21 processing
│   │   └── storage.py       # excerpt folders + meta.json
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── index.html
│   └── src/
│       ├── main.ts
│       ├── api.ts
│       ├── score/render.ts      # Verovio wrapper
│       ├── score/editor.ts      # MEI edits
│       ├── playback/player.ts   # Tone.js scheduling
│       ├── playback/sounds.ts   # violin / piano / pure tone
│       └── ui/                  # toolbar, library, side-by-side view
├── scripts/
│   ├── fetch_samples.py     # download VSCO 2 CE violin samples
│   └── omr_eval.py          # accuracy benchmark (milestone 6)
└── data/                    # gitignored
    ├── samples/
    └── excerpts/<id>/
        ├── original.<ext>
        ├── pages/page-1.png ...
        ├── omr/<engine>.musicxml
        ├── score.musicxml   # normalized
        ├── score.mei        # working copy with edits
        └── meta.json        # title, engine, tempo, created, settings
```

## Backend API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/excerpts` | Multipart upload: file, `engine` (`audiveris`/`homr`/`auto`), `accidental_rule` (`bar`/`note`). Runs the pipeline and returns the excerpt. |
| `GET` | `/api/excerpts` | List the library |
| `GET` | `/api/excerpts/{id}` | Metadata |
| `GET` | `/api/excerpts/{id}/pages/{n}` | Page image |
| `GET` | `/api/excerpts/{id}/score?format=musicxml\|mei` | Score |
| `PUT` | `/api/excerpts/{id}/score` | Save MEI working copy |
| `POST` | `/api/excerpts/{id}/reset` | Discard edits, go back to the normalized MusicXML |
| `POST` | `/api/excerpts/{id}/rerun` | Re-run OMR with a different engine or settings |
| `PATCH` | `/api/excerpts/{id}` | Update title, tempo override, etc. |
| `DELETE` | `/api/excerpts/{id}` | Delete |
| `GET` | `/api/health` | Reports which OMR engines are installed |

OMR can take 10–60 s. The MVP can block the request with a spinner in the UI. If that becomes a problem, switch to a background task with a status endpoint.

## Pipeline details

**PDF/images:** render PDF pages at 300 DPI. For an image, apply EXIF rotation.

**Cleanup:** convert to grayscale, deskew (estimate staff-line angle with a Hough transform), and add an optional adaptive threshold. Phone photos get perspective correction when a page contour is found. Keep each step toggleable, because cleanup can make clean PDFs worse.

**OMR engine interface:**

```python
class OMREngine(Protocol):
    name: str
    def available(self) -> bool: ...
    def run(self, image_paths: list[Path], out_dir: Path) -> Path:  # returns MusicXML path
        ...
```

- **Audiveris:** call the binary via `subprocess` in batch mode with export (roughly `Audiveris -batch -export -output <dir> -- <input>`; check the flags against the installed version). It may output `.mxl` (compressed), so unzip it. Default binary path on macOS is `/Applications/Audiveris.app/Contents/MacOS/Audiveris`, overridable in config or by an env var.
- **homr:** run per page image via its CLI or Python entry point. Merge multi-page results with music21 when there's more than one page.
- **auto:** use Audiveris for PDFs and homr for photos. Fall back to the other engine if one fails or returns an empty score.

**Normalize (music21):**

- If there are multiple parts, keep them all, but flag the violin part (or the first part) as the playback default.
- Find the tempo: look for a `MetronomeMark`. If there isn't one, look for text expressions like "♩ = 72", "q=72", or "Allegro (♩=132)" using a regex. If nothing turns up, use 80 BPM and set `tempo_source: "default"` in meta so the UI prompts the user to enter the printed tempo.
- **Accidental rule `note`:** for contemporary scores where an accidental applies only to its own note, walk each measure and set later notes of the same step/octave without a written accidental back to natural. Default is `bar` (traditional).
- Write `score.musicxml`.

## Frontend

**Layout:**

- Left sidebar: excerpt library and upload button.
- Main area: split view with the original page image on the left (zoom and pan) and the rendered score on the right. Can be toggled to score-only.
- Bottom transport bar:
  - Play/pause/stop
  - Tempo: BPM field showing the marked tempo, and a slider from 25% to 150%
  - Loop toggle
  - Count-in (0/1/2 bars)
  - Metronome click on/off
  - Sound: violin / piano / pure tone
  - Volume

**Playback (`player.ts`):**

- Build a list of note events from the timemap: `{id, startMs, endMs, midi, measureId}`. Get `measureId` by walking up the SVG from the note's element to its `g.measure`.
- Schedule on `Tone.Transport`, with times multiplied by `100 / tempoPercent`. Changing tempo during playback reschedules from the current position.
- Range selection: click a measure to select it, shift-click to extend the range. Play and loop only the events in that range.
- Cursor: add a `playing` CSS class to the note's SVG element on note-on and remove it on note-off. Auto-scroll the score.
- Ties: Verovio's timemap already merges tied notes. Check this with a test score.
- Grace notes and unusual tuplets should play in time. Skip anything Verovio can't time and log a console warning.

**Practice tools:**

- **Step mode:** left/right arrow keys move note by note (or chord by chord) and play each one, sustained, until the next key press.
- **Drone:** pick a note (or click one in the score) and hold it continuously while the user plays along.
- **Pure tone and piano sounds:** dissonant intervals are often clearer without violin vibrato or timbre.

**Correction mode:**

- Click a note to select it (highlighted).
- Keys:
  - `↑`/`↓`: step the pitch up or down by staff position
  - `Shift+↑/↓`: octave
  - `#`, `b`, `n`: set accidental to sharp/flat/natural
  - `0`: remove the accidental
  - `1`–`7`: duration from whole to 64th
  - `.`: toggle dot
  - `Delete`: turn the note into a rest
- Play the note after every edit so the change is heard right away.
- Undo/redo stack of MEI snapshots.
- Autosave via PUT, debounced to 1 s.
- Clicking a measure in the score highlights the rough matching area on the original image. This is an MVP nice-to-have: an approximate mapping by measure order and system position is fine. Exact mapping is out of scope.

## Sounds

- `scripts/fetch_samples.py` downloads VSCO 2 Community Edition solo violin sustain samples (CC0) into `data/samples/violin/`, then writes a JSON map of note name → file for `Tone.Sampler`. Every 3rd semitone across G3–E7 is enough. The sampler pitch-shifts between samples.
- Piano: a small free set like Salamander (check the license, then credit it in the README), or skip piano for the MVP.
- Pure tone: `Tone.Synth` with a sine or triangle wave and a short envelope. No samples needed.
- If samples are missing, fall back to pure tone and show a notice to run `make setup`.

## Mac setup (goes in README)

```bash
brew install uv node
```

Install Audiveris from its GitHub releases page (the macOS `.dmg`). Recent releases bundle Java. On first launch, macOS may need it allowed under System Settings → Privacy & Security.

```bash
make setup    # uv sync, npm install, fetch samples
make start    # builds the frontend, starts the server, opens the browser
make dev      # uvicorn --reload + vite dev server with proxy
make test
```

## Milestones

Each one should end with the app runnable and the acceptance checks passing. Commit after each milestone.

**M1 — Skeleton**
- uv project, FastAPI app, Vite frontend, served together, Makefile.
- `/api/health` reports Audiveris and homr availability.
- Accept: `make start` opens the browser to a page showing engine status.

**M2 — Import pipeline**
- Upload, PDF→PNG, cleanup, both OMR engines, normalize, storage, library listing.
- Accept: uploading a clean single-page violin PDF produces `score.musicxml`, and the excerpt appears in the library. Tests cover normalize (tempo detection, accidental rule) using MusicXML fixtures built with music21. The tests don't need OMR installed.

**M3 — Render + playback**
- Verovio rendering, side-by-side original image, Tone.js playback with violin samples, tempo field and slider, cursor.
- Accept: a known MusicXML fixture plays the correct pitches in order at the marked tempo. Doubling the slider halves the duration.

**M4 — Practice tools**
- Measure range selection, loop, count-in, metronome, step mode, drone, sound switch.
- Accept: selecting bars 3–5 and pressing play loops exactly those bars at the chosen tempo.

**M5 — Correction mode**
- MEI working copy, note editing keys, undo/redo, autosave, reset to OMR result, re-run with the other engine.
- Accept: change a note's pitch and accidental, reload the page, and the edit is still there and plays back correctly.

**M6 — OMR quality**
- `scripts/omr_eval.py`: render known MusicXML files to PNG with Verovio's Python package, run each engine on them, and report per-measure pitch and rhythm accuracy. Include a few deliberately contemporary-style test scores (no key signature, dense accidentals, 5/8 and 7/16, nested tuplets).
- Run both engines on an upload and flag measures where they disagree (a colored outline in the score) so the user knows where to check.
- Accept: the eval script prints an accuracy table for both engines.

## Out of scope for now

- Pitch detection of the user's own playing (planned later: aubio or CREPE)
- Realistic neural violin (DDSP)
- Microtonal playback. Render quarter-tone accidentals if Verovio shows them, but playback can round to the nearest semitone and show a warning.
- Mobile/iOS, hosting, multiple users
- Full score editing (adding measures, changing meters)

## Notes for the builder

- Keep the frontend dependency-light. Tone.js and Verovio are the only big runtime deps.
- Don't commit samples, user data, or large binaries. `data/` is gitignored.
- Write backend tests with generated MusicXML fixtures, not real copyrighted excerpts.
- Before adding something not listed here, check with the user.
