import * as Tone from "tone";
import { getScore, pageUrl, scoreUrl, updateExcerpt, type Excerpt } from "../api";
import { Player } from "../playback/player";
import { createPureTone, createViolin, type Sound } from "../playback/sounds";
import { buildTimeline, timeScale } from "../playback/timeline";
import { ScoreView } from "../score/render";
import { el } from "./dom";
import { createTransport } from "./transport";

const ENGINE_NAMES: Record<string, string> = { audiveris: "Audiveris", homr: "homr" };

export interface ExcerptView {
  element: HTMLElement;
  dispose(): void;
}

export interface ExcerptHandlers {
  onDelete(excerpt: Excerpt): void;
  onChange(excerpt: Excerpt): void;
}

/** 0–100 slider position to decibels, with silence at the bottom. */
const volumeToDb = (volume: number) => (volume <= 0 ? -Infinity : 20 * Math.log10(volume / 100) * 1.5);

export function createExcerptView(excerpt: Excerpt, handlers: ExcerptHandlers): ExcerptView {
  let disposed = false;
  let player: Player | null = null;
  let score: ScoreView | null = null;
  let bpm = excerpt.tempo_bpm;
  let percent = 100;
  let baseQpm = 120;
  const lit = new Set<string>();
  const sounds: Sound[] = [];
  const output = new Tone.Volume(volumeToDb(80)).toDestination();

  // --- header ---------------------------------------------------------------

  const remove = el("button", { type: "button", class: "danger", textContent: "Delete" });
  remove.addEventListener("click", () => {
    if (confirm(`Delete "${excerpt.title}"? The upload and its score are removed.`)) handlers.onDelete(excerpt);
  });
  const layoutToggle = el("button", { type: "button", textContent: "Score only" });
  layoutToggle.setAttribute("aria-pressed", "false");

  const summary = [
    `Read by ${ENGINE_NAMES[excerpt.engine] ?? excerpt.engine}`,
    `${excerpt.measure_count} bars`,
    `${excerpt.note_count} notes`,
    excerpt.accidental_rule === "note" ? "accidentals apply to their own note" : null,
    excerpt.parts.length > 1 ? `playing ${excerpt.parts[excerpt.playback_part]?.name}` : null,
  ].filter(Boolean).join(" · ");

  // --- original pages ---------------------------------------------------------

  let zoom = 100;
  const pages = el("div", { class: "pages" });
  for (let page = 1; page <= excerpt.page_count; page++) {
    pages.append(el("img", { src: pageUrl(excerpt.id, page), alt: `Page ${page} of ${excerpt.original_filename}` }));
  }
  const zoomLabel = el("span", { class: "zoom-label", textContent: "100%" });
  const setZoom = (value: number) => {
    zoom = Math.min(400, Math.max(50, value));
    pages.style.width = `${zoom}%`;
    zoomLabel.textContent = `${zoom}%`;
  };
  const zoomOut = el("button", { type: "button", textContent: "−" });
  const zoomIn = el("button", { type: "button", textContent: "+" });
  zoomOut.setAttribute("aria-label", "Zoom out");
  zoomIn.setAttribute("aria-label", "Zoom in");
  zoomOut.addEventListener("click", () => setZoom(zoom - 25));
  zoomIn.addEventListener("click", () => setZoom(zoom + 25));

  const originalPane = el(
    "section",
    { class: "pane original" },
    el("div", { class: "pane-head" }, el("span", { textContent: "Original" }), zoomOut, zoomLabel, zoomIn),
    el("div", { class: "pane-body" }, pages),
  );

  // --- rendered score -----------------------------------------------------------

  const scoreHost = el("div", { class: "score" });
  const scoreStatus = el("p", { class: "status busy", textContent: "Rendering the score…" });
  const scoreBody = el("div", { class: "pane-body" }, scoreStatus, scoreHost);
  const scorePane = el(
    "section",
    { class: "pane rendered" },
    el("div", { class: "pane-head" }, el("span", { textContent: "Read score" })),
    scoreBody,
  );

  const split = el("div", { class: "split" }, originalPane, scorePane);
  layoutToggle.addEventListener("click", () => {
    const scoreOnly = split.classList.toggle("score-only");
    layoutToggle.setAttribute("aria-pressed", String(scoreOnly));
    layoutToggle.textContent = scoreOnly ? "Side by side" : "Score only";
  });

  // --- transport ------------------------------------------------------------------

  const applyScale = () => player?.setScale(timeScale(baseQpm, bpm * excerpt.tempo_beat, percent));

  const transport = createTransport(
    { bpm, beat: excerpt.tempo_beat, isPlaceholder: excerpt.tempo_source === "default" },
    {
      onPlayPause: () => {
        if (!player) return;
        if (player.getState() === "playing") player.pause();
        else void player.play();
      },
      onStop: () => player?.stop(),
      onBpm: (value) => {
        bpm = value;
        applyScale();
        updateExcerpt(excerpt.id, { tempo_bpm: value })
          .then((updated) => !disposed && handlers.onChange(updated))
          .catch((err: Error) => !disposed && transport.setNotice(`The tempo wasn't saved: ${err.message}`));
      },
      onPercent: (value) => {
        percent = value;
        applyScale();
      },
      onVolume: (value) => {
        output.volume.value = volumeToDb(value);
      },
    },
  );

  const onKey = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement | null;
    if (event.code !== "Space" || !player || target?.closest("input, button, select, textarea, a")) return;
    event.preventDefault();
    if (player.getState() === "playing") player.pause();
    else void player.play();
  };
  document.addEventListener("keydown", onKey);

  // --- cursor ---------------------------------------------------------------------

  const follow = (note: Element) => {
    const box = note.getBoundingClientRect();
    const view = scoreBody.getBoundingClientRect();
    if (box.top < view.top + 40 || box.bottom > view.bottom - 40) {
      scoreBody.scrollTo({
        top: scoreBody.scrollTop + box.top - view.top - view.height / 3,
        behavior: "smooth",
      });
    }
  };
  const onMark = (id: string, on: boolean) => {
    if (on) lit.add(id);
    else lit.delete(id);
    const note = score?.element(id);
    if (!note) return;
    note.classList.toggle("playing", on);
    if (on) follow(note);
  };

  let resizeTimer = 0;
  const resize = new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      if (!score || scoreHost.clientWidth === 0) return;
      score.layout();
      for (const id of lit) score.element(id)?.classList.add("playing");
    }, 150);
  });

  // --- load -------------------------------------------------------------------------

  async function load(): Promise<void> {
    const xml = await getScore(excerpt.id);
    const view = await ScoreView.create(scoreHost, xml);
    if (disposed) return view.dispose();
    score = view;
    scoreStatus.remove();
    resize.observe(scoreHost);

    const staff = excerpt.parts.length > 1 ? excerpt.playback_part + 1 : undefined;
    const timeline = buildTimeline(view.timemap(), (id) => view.midiOf(id), view.mei(), staff);
    baseQpm = timeline.baseQpm;

    const tone = createPureTone(output);
    sounds.push(tone);
    player = new Player(timeline, tone, { onMark, onState: (state) => transport.setState(state) });
    applyScale();
    transport.setReady(timeline.notes.length > 0);

    const violin = await createViolin(output);
    if (disposed) return violin?.dispose();
    if (violin) {
      sounds.push(violin);
      player.setSound(violin);
    } else {
      transport.setNotice("Violin samples aren't installed, so this plays a plain tone. Run `make setup` to get them.");
    }
  }

  load().catch((err: Error) => {
    if (disposed) return;
    scoreStatus.className = "status error";
    scoreStatus.textContent = err.message;
  });

  const element = el(
    "article",
    { class: "excerpt" },
    el(
      "header",
      { class: "detail-head" },
      el("div", { class: "detail-title" }, el("h1", { textContent: excerpt.title }), el("p", { class: "summary", textContent: summary })),
      layoutToggle,
      el("a", { class: "button", href: scoreUrl(excerpt.id), download: `${excerpt.title}.musicxml`, textContent: "MusicXML" }),
      remove,
    ),
    excerpt.warnings.length > 0 &&
      el("ul", { class: "warnings" }, ...excerpt.warnings.map((w) => el("li", { textContent: w }))),
    split,
    transport.element,
  );

  return {
    element,
    dispose() {
      disposed = true;
      document.removeEventListener("keydown", onKey);
      clearTimeout(resizeTimer);
      resize.disconnect();
      player?.dispose();
      for (const sound of sounds) sound.dispose();
      output.dispose();
      score?.dispose();
    },
  };
}
