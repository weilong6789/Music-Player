import * as Tone from "tone";
import { getSamples } from "../api";
import { midiToFrequency } from "./timeline";

export interface Sound {
  /** "violin" when the samples loaded, "tone" for the fallback. */
  kind: "violin" | "tone";
  play(midi: number, durationSec: number, time: number): void;
  releaseAll(): void;
  dispose(): void;
}

function wrap(kind: Sound["kind"], instrument: Tone.Sampler | Tone.PolySynth): Sound {
  return {
    kind,
    play: (midi, duration, time) =>
      instrument.triggerAttackRelease(midiToFrequency(midi), duration, time),
    releaseAll: () => instrument.releaseAll(),
    dispose: () => instrument.dispose(),
  };
}

export function createPureTone(output: Tone.InputNode): Sound {
  const synth = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: "triangle" },
    envelope: { attack: 0.02, decay: 0.05, sustain: 0.9, release: 0.08 },
  });
  synth.volume.value = -8;
  synth.connect(output);
  return wrap("tone", synth);
}

/** The sampled violin, or null when the samples aren't installed or fail to load. */
export async function createViolin(output: Tone.InputNode): Promise<Sound | null> {
  let info;
  try {
    info = (await getSamples()).violin;
  } catch {
    return null;
  }
  if (!info.available) return null;

  return new Promise((resolve) => {
    const sampler: Tone.Sampler = new Tone.Sampler({
      urls: info.notes,
      baseUrl: info.base_url,
      attack: 0.01,
      release: 0.12,
      onload: () => resolve(wrap("violin", sampler)),
      onerror: () => {
        sampler.dispose();
        resolve(null);
      },
    });
    sampler.connect(output);
  });
}
