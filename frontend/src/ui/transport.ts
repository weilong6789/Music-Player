import type { PlayerState } from "../playback/player";
import { el } from "./dom";

const BEAT_SYMBOLS: Record<string, string> = {
  "0.5": "♪",
  "1": "♩",
  "1.5": "♩.",
  "2": "half note",
  "3": "dotted half",
};

export const MIN_BPM = 20;
export const MAX_BPM = 400;

export interface TransportHandlers {
  onPlayPause(): void;
  onStop(): void;
  /** A valid BPM was entered. */
  onBpm(bpm: number): void;
  onPercent(percent: number): void;
  /** 0–100 */
  onVolume(volume: number): void;
}

export interface Transport {
  element: HTMLElement;
  setState(state: PlayerState): void;
  setReady(ready: boolean): void;
  setNotice(text: string | null): void;
}

export function createTransport(
  tempo: { bpm: number; beat: number; isPlaceholder: boolean },
  handlers: TransportHandlers,
): Transport {
  const play = el("button", { type: "button", class: "primary play", textContent: "Play", disabled: true });
  const stop = el("button", { type: "button", textContent: "Stop", disabled: true });
  play.addEventListener("click", handlers.onPlayPause);
  stop.addEventListener("click", handlers.onStop);

  const bpm = el("input", {
    type: "number",
    class: "bpm",
    min: String(MIN_BPM),
    max: String(MAX_BPM),
    step: "1",
    value: String(Math.round(tempo.bpm)),
  });
  bpm.setAttribute("aria-label", "Tempo in beats per minute");
  const hint = el("span", {
    class: "tempo-hint",
    textContent: "No tempo marking was read. Enter the printed one.",
    hidden: !tempo.isPlaceholder,
  });
  bpm.addEventListener("change", () => {
    const value = Number(bpm.value);
    const valid = Number.isFinite(value) && value >= MIN_BPM && value <= MAX_BPM;
    bpm.classList.toggle("invalid", !valid);
    if (!valid) return;
    hint.hidden = true;
    handlers.onBpm(value);
  });

  const percentLabel = el("output", { class: "percent", textContent: "100%" });
  const percent = el("input", { type: "range", min: "25", max: "150", step: "5", value: "100" });
  percent.setAttribute("aria-label", "Speed as a percentage of the tempo");
  percent.addEventListener("input", () => {
    percentLabel.textContent = `${percent.value}%`;
    handlers.onPercent(Number(percent.value));
  });

  const volume = el("input", { type: "range", min: "0", max: "100", step: "1", value: "80" });
  volume.setAttribute("aria-label", "Volume");
  volume.addEventListener("input", () => handlers.onVolume(Number(volume.value)));

  const notice = el("p", { class: "transport-notice", hidden: true });

  const element = el(
    "footer",
    { class: "transport" },
    el("div", { class: "transport-row" },
      el("div", { class: "group" }, play, stop),
      el("label", { class: "group" },
        el("span", { class: "beat", textContent: `${BEAT_SYMBOLS[String(tempo.beat)] ?? "beat"} =` }),
        bpm,
      ),
      el("label", { class: "group grow" }, el("span", { textContent: "Speed" }), percent, percentLabel),
      el("label", { class: "group" }, el("span", { textContent: "Volume" }), volume),
    ),
    hint,
    notice,
  );

  return {
    element,
    setState(state) {
      play.textContent = state === "playing" ? "Pause" : "Play";
      stop.disabled = state === "stopped";
    },
    setReady(ready) {
      play.disabled = !ready;
    },
    setNotice(text) {
      notice.hidden = !text;
      notice.textContent = text ?? "";
    },
  };
}
