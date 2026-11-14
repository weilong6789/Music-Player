import { pageUrl, scoreUrl, type Excerpt } from "../api";
import { el } from "./dom";

const BEAT_SYMBOLS: Record<string, string> = {
  "0.5": "♪",
  "1": "♩",
  "1.5": "♩.",
  "2": "half note",
  "3": "dotted half",
};

const ENGINE_NAMES: Record<string, string> = { audiveris: "Audiveris", homr: "homr" };

function tempoText(excerpt: Excerpt): string {
  const beat = BEAT_SYMBOLS[String(excerpt.tempo_beat)] ?? "beat";
  const bpm = Math.round(excerpt.tempo_bpm);
  return excerpt.tempo_source === "default"
    ? `${beat} = ${bpm} (no tempo marking was read; this is a placeholder)`
    : `${beat} = ${bpm}`;
}

function fact(label: string, value: string): HTMLElement {
  return el("div", { class: "fact" }, el("dt", { textContent: label }), el("dd", { textContent: value }));
}

export function renderDetail(excerpt: Excerpt, onDelete: (excerpt: Excerpt) => void): HTMLElement {
  const remove = el("button", { type: "button", class: "danger", textContent: "Delete" });
  remove.addEventListener("click", () => {
    if (confirm(`Delete "${excerpt.title}"? The upload and its score are removed.`)) onDelete(excerpt);
  });

  const facts = el(
    "dl",
    { class: "facts" },
    fact("Read by", ENGINE_NAMES[excerpt.engine] ?? excerpt.engine),
    fact("Bars", String(excerpt.measure_count)),
    fact("Notes", String(excerpt.note_count)),
    fact("Tempo", tempoText(excerpt)),
    fact("Accidentals", excerpt.accidental_rule === "note" ? "Only their own note" : "Carry through the bar"),
    excerpt.parts.length > 1 &&
      fact("Parts", excerpt.parts.map((p) => p.name).join(", ")),
    excerpt.cleanup_applied.length > 0 && fact("Cleanup", excerpt.cleanup_applied.join(", ")),
  );

  const pages = el("div", { class: "pages" });
  for (let page = 1; page <= excerpt.page_count; page++) {
    pages.append(
      el("img", {
        src: pageUrl(excerpt.id, page),
        alt: `Page ${page} of ${excerpt.original_filename}`,
        loading: "lazy",
      }),
    );
  }

  return el(
    "article",
    { class: "detail" },
    el(
      "header",
      { class: "detail-head" },
      el("h1", { textContent: excerpt.title }),
      el("a", { class: "button", href: scoreUrl(excerpt.id), download: `${excerpt.title}.musicxml`, textContent: "MusicXML" }),
      remove,
    ),
    facts,
    excerpt.warnings.length > 0 &&
      el("ul", { class: "warnings" }, ...excerpt.warnings.map((w) => el("li", { textContent: w }))),
    pages,
  );
}
