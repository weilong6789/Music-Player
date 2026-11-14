# Sheet Music Player — Brainstorm

## Goal

Upload a scanned or photographed audition excerpt (usually a violin part, sometimes a solo), have it read into notes, then play it back so I can check what it's supposed to sound like.

Two kinds of material:

- **Standard rep** (Pictures at an Exhibition, etc.): recordings exist, so the tool mostly saves time — jump to the exact excerpt and slow it down.
- **Contemporary pieces**: heavy dissonance, no recordings, hard to tell by ear if I'm right. This is the case that actually needs the tool.

Must-haves:

1. Upload a scan/photo/PDF of the excerpt
2. Convert it to playable notes (optical music recognition, OMR)
3. Play it back with a violin sound
4. Use the printed tempo marking by default, with a tempo slider
5. Select a range of measures (or drag over notes) and play/loop just that
6. Fix mistakes the scanner made before trusting the playback

## The pipeline

```
scan / photo / PDF
      │
      ▼
 image cleanup (deskew, crop, contrast)
      │
      ▼
 OMR  ──►  MusicXML
      │
      ▼
 correction step (show rendered score next to the original image, let me fix notes)
      │
      ▼
 render score + playback (tempo, measure selection, loop, cursor)
```

The OMR step is the weak link. Every OMR engine makes mistakes, and contemporary scores make it worse: irregular meters, nested tuplets, lots of accidentals, no key signature, extended techniques, sometimes quarter-tones. A playback tool that plays wrong notes confidently is worse than nothing for the "is this dissonance right?" question, so a quick way to see and fix errors is a core feature, not a nice-to-have.

One specific thing to handle: many contemporary scores use the convention that an accidental applies only to the note it's attached to (not the rest of the bar). OMR and MusicXML playback assume the traditional rule. Needs a toggle.

## Platform options

| Option | Pros | Cons |
|---|---|---|
| **Web app / PWA** | Works on laptop, iPad on a music stand, and phone. Phone camera upload works in the browser. One codebase. Can be "installed" to home screen. | OMR has to run on a server (the good engines are Java/Python), so need hosting. |
| **Native iOS/iPadOS app** | Apple's VisionKit document scanner gives great cropping/deskew for free. Best feel on iPad. | Swift only, App Store hassle, OMR still probably server-side or a slow on-device model. |
| **Desktop app (Tauri or Electron)** | Can bundle Audiveris locally, no server, works offline. | Not on the iPad/phone where I'd actually practice. |
| **Local Python tool (Gradio / Streamlit)** | Fastest to build. Good for proving the OMR + playback pipeline works. | Ugly, laptop-only unless hosted. |
| **MuseScore + plugin / workflow** | MuseScore 4 already imports PDFs (via its online Audiveris-based importer), has a free realistic violin (Muse Sounds), tempo control, and loop playback. | Not a custom app, clunky for quick audition prep, import quality varies. Worth trying first as the baseline. |

**Recommendation:** start with a Python prototype (Gradio) to test which OMR engine handles my actual excerpts, then build a PWA: Python backend for OMR, browser frontend for rendering, correction, and playback. Host the backend somewhere cheap (Hugging Face Spaces, Fly.io, Railway, or just my own machine).

## Existing tools to try before building anything

These tell me how good the state of the art is on my own scans.

- **PlayScore 2** (iOS/Android): photo → playback with tempo control. Probably the closest existing product to this idea. Good for benchmarking.
- **Soundslice**: has a sheet music scanner (PDF/photo → editable notation) plus excellent practice playback (loop, slow down). Paid.
- **MuseScore 4 + musescore.com PDF import**: free, Audiveris under the hood, Muse Sounds violin is genuinely good.
- **Newzik**: score reader with "Maestria" OMR, aimed at orchestral musicians.
- **ScanScore / SmartScore / PhotoScore**: desktop OMR, commercial.

If one of these already handles contemporary excerpts well, the custom app can focus on the practice UX instead of OMR.

## OMR (image → notes)

- **Audiveris** — the main open source OMR engine. Java. Outputs MusicXML. Best on clean printed scans, less good on phone photos. Has a CLI so it can run headless on a server. AGPL.
- **homr** — Python, transformer-based, designed for camera photos of sheet music. Outputs MusicXML. Newer and actively worked on.
- **oemer** — Python, deep learning end-to-end OMR, also handles photos. Outputs MusicXML. Slower, CPU works.
- **Sheet Music Transformer (SMT) and similar research models** — end-to-end image → notation models from the research community. Worth watching, not production-ready.
- **Vision LLMs** (Claude, GPT, Gemini) — can read short excerpts and output MusicXML/ABC/LilyPond. Unreliable on dense passages but useful as a second opinion or for reading text like tempo markings, "sul pont.", etc. Could be a fallback or a cross-check: run two engines and flag measures where they disagree.

Image cleanup before OMR: **OpenCV** (deskew, perspective correction, thresholding), or on iOS, **VisionKit**. Phone photos of audition PDFs printed out and marked up in pencil will need this.

## Score parsing and manipulation

- **music21** (Python) — parse MusicXML, pull out measure ranges, change tempo, transpose, apply accidental rules, export MIDI. Very useful on the backend.
- **partitura** (Python) — similar, more performance/alignment oriented.
- **pretty_midi / mido** — low-level MIDI handling if needed.

## Rendering the score in the browser

- **Verovio** — C++ compiled to WebAssembly. Renders MusicXML/MEI to SVG, also outputs MIDI and a timemap (which note sounds at which millisecond), which is exactly what's needed for a moving cursor and clicking a measure to play from it. Strong pick.
- **OpenSheetMusicDisplay (OSMD)** — renders MusicXML via VexFlow, has a built-in cursor. Official playback is a paid add-on, but there's an older community `osmd-audio-player`.
- **alphaTab** — renders MusicXML (not just guitar tab), has a built-in SoundFont player, cursor, tempo control, and loop selection out of the box. Could cover rendering + playback + measure selection in one library. Worth prototyping alongside Verovio.
- **VexFlow** — low-level notation drawing, only if I want full control.
- **abcjs** — renders ABC notation with built-in synth. Simple, but MusicXML → ABC conversion loses things.

## Playback / violin sound

Web audio engines:

- **SpessaSynth** — modern SoundFont2/3 synth in JS, plays MIDI in the browser.
- **smplr** — plays sample libraries in the browser, simple API.
- **Tone.js** — scheduling, tempo changes (Transport BPM), looping. Good for the timing layer even if samples come from elsewhere.
- **js-synthesizer** — FluidSynth compiled to WebAssembly.
- **WebAudioFont** — lots of GM instruments, quick to set up.

Violin samples / SoundFonts:

- **VSCO 2 Community Edition** (Versilian) — CC0, solo violin with sustain, staccato, pizz. Free to bundle.
- **Sonatina Symphonic Orchestra** — older free orchestral samples, includes violin.
- **University of Iowa Musical Instrument Samples** — free, individual violin notes, would need mapping into a sampler.
- **MuseScore_General SoundFont / FluidR3_GM** — general MIDI, violin is passable, not great.

For dissonant contemporary music, **pitch accuracy matters more than realism.** A clean, slightly synthetic violin (or even a piano/sine option) makes intervals easier to hear than a realistic one with vibrato. Worth having a timbre switch: violin / piano / pure tone.

Making it sound more like a real violin (later):

- **DDSP / MIDI-DDSP** (Google Magenta) — neural synthesis trained on violin, turns MIDI into fairly convincing violin audio with expression. Python, server-side render.
- **Desktop route**: render MIDI through a real sample library offline (Muse Sounds, BBC SO Discover, Spitfire LABS) — not usable in a browser, but fine for a "render high-quality audio" button on a desktop build.

## Practice features

Core:

- Tempo from the printed marking, editable (OMR often misses metronome marks, so a manual field is needed)
- Tempo slider (percent of marked tempo, or absolute BPM)
- Click a measure / drag a range → play or loop that section
- Moving cursor/highlight following playback
- Count-in and optional metronome click
- Side-by-side: original scan image and rendered score, so OMR errors are obvious

Useful for contemporary pieces specifically:

- Play one note or chord at a time (step through with arrow keys) to check intervals slowly
- Hold/drone a note while I play against it
- Accidental rule toggle (per-note vs per-bar)
- Handle tempo changes, meter changes, and metric modulations in the piece
- Flag measures where OMR confidence is low or two engines disagree

Later:

- Pitch detection while I play (**pitchy**, **CREPE**, **aubio**, **ml5.js**) to show where I'm out of tune or wrong compared to the score
- Save a library of excerpts per audition
- Export MIDI / audio to listen away from the app
- Play the excerpt with other parts if I have them (full score excerpts)

## Rough build plan

1. **Benchmark (no code):** run 5–10 real excerpts, including a couple of the nastiest contemporary ones, through PlayScore 2, MuseScore import, and Soundslice. Note what breaks.
2. **Prototype (Python + Gradio):** upload image → run Audiveris and homr → show MusicXML rendered → music21 to MIDI → play with a violin SoundFont. Tempo slider and measure range inputs. Goal: find out which OMR engine wins on my material.
3. **Web app MVP:** FastAPI backend (OMR + music21), frontend with Verovio or alphaTab, SpessaSynth/Tone.js playback, measure selection, tempo, loop. PWA so it installs on the iPad.
4. **Correction UI:** click a note to change pitch/accidental/duration, re-render instantly. This is the hard part of the frontend.
5. **Extras:** pitch detection, excerpt library, better violin sound.

## Open questions

- How often are my excerpts clean PDFs vs phone photos of printed pages? That decides how much effort goes into image cleanup and which OMR engine to favor.
- Do I want offline use (practice rooms with bad wifi)? That pushes toward a desktop build or on-device OMR.
- How much editing am I willing to do per excerpt? If a minute of fixing is fine, a mediocre OMR engine plus a good correction UI beats chasing perfect recognition.
