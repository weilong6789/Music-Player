/** Turns Verovio's timemap into what the player needs. No audio or DOM in here. */

export interface TimemapEntry {
  tstamp: number;
  qstamp: number;
  on?: string[];
  off?: string[];
  tempo?: number;
}

/** A sounding note. Tied notes are merged into one. */
export interface NoteEvent {
  id: string;
  startMs: number;
  endMs: number;
  midi: number;
}

/** A notehead to highlight. Every printed note has one, tied or not. */
export interface Mark {
  id: string;
  startMs: number;
  endMs: number;
}

export interface Timeline {
  notes: NoteEvent[];
  marks: Mark[];
  durationMs: number;
  /** Quarter notes per minute that the timemap's opening was timed at. */
  baseQpm: number;
}

const DEFAULT_QPM = 120;

export function buildTimeline(
  timemap: TimemapEntry[],
  midiOf: (id: string) => number | undefined,
  mei: string,
  staff?: number,
): Timeline {
  const staffOf = staff === undefined ? null : noteStaves(mei);
  // A staff with nothing on it would mean silence; play everything instead.
  const useStaff = staffOf !== null && [...staffOf.values()].includes(staff!);
  const included = (id: string) => !useStaff || staffOf!.get(id) === staff;

  const open = new Map<string, number>();
  const spans = new Map<string, Mark>();
  let durationMs = 0;
  for (const entry of timemap) {
    durationMs = Math.max(durationMs, entry.tstamp);
    for (const id of entry.off ?? []) {
      const start = open.get(id);
      if (start === undefined) continue;
      open.delete(id);
      spans.set(id, { id, startMs: start, endMs: entry.tstamp });
    }
    for (const id of entry.on ?? []) {
      if (included(id)) open.set(id, entry.tstamp);
    }
  }
  for (const [id, start] of open) spans.set(id, { id, startMs: start, endMs: durationMs });

  const marks = [...spans.values()].sort((a, b) => a.startMs - b.startMs);

  // Verovio times each tied note separately, so join the chain into one sounding note.
  const tiedTo = tieTargets(mei);
  const absorbed = new Set<string>();
  const notes: NoteEvent[] = [];
  for (const mark of marks) {
    if (absorbed.has(mark.id)) continue;
    const midi = midiOf(mark.id);
    if (midi === undefined) {
      console.warn(`No pitch for ${mark.id}; skipping it`);
      continue;
    }
    let endMs = mark.endMs;
    let next = tiedTo.get(mark.id);
    while (next !== undefined && spans.has(next) && !absorbed.has(next)) {
      absorbed.add(next);
      endMs = Math.max(endMs, spans.get(next)!.endMs);
      next = tiedTo.get(next);
    }
    notes.push({ id: mark.id, startMs: mark.startMs, endMs, midi });
  }

  return { notes, marks, durationMs, baseQpm: openingQpm(timemap) };
}

/** Tempo of the opening in quarter notes per minute, measured from the timemap itself. */
export function openingQpm(timemap: TimemapEntry[]): number {
  const first = timemap[0];
  if (!first) return DEFAULT_QPM;
  const next = timemap.find((e) => e.tstamp > first.tstamp && e.qstamp > first.qstamp);
  if (!next) return first.tempo ?? DEFAULT_QPM;
  // Timestamps are whole milliseconds, so the stated tempo is more exact when the two agree.
  const measured = (60000 * (next.qstamp - first.qstamp)) / (next.tstamp - first.tstamp);
  const stated = first.tempo;
  return stated && Math.abs(stated - measured) / measured < 0.02 ? stated : measured;
}

/**
 * Factor from timemap milliseconds to playback milliseconds.
 * `targetQpm` is the tempo wanted for the opening; later tempo changes keep their proportion.
 */
export function timeScale(baseQpm: number, targetQpm: number, percent: number): number {
  return (baseQpm / targetQpm) * (100 / percent);
}

/** Tie start note id → the note it's tied to. */
export function tieTargets(mei: string): Map<string, string> {
  const targets = new Map<string, string>();
  for (const [tag] of mei.matchAll(/<tie\b[^>]*>/g)) {
    const start = /\bstartid="#([^"]+)"/.exec(tag)?.[1];
    const end = /\bendid="#([^"]+)"/.exec(tag)?.[1];
    if (start && end) targets.set(start, end);
  }
  return targets;
}

/** Note id → number of the staff it's written on. */
export function noteStaves(mei: string): Map<string, number> {
  const staves = new Map<string, number>();
  let current = 1;
  for (const match of mei.matchAll(/<staff\b[^>]*\bn="(\d+)"|<note\b[^>]*\bxml:id="([^"]+)"/g)) {
    if (match[1] !== undefined) current = Number(match[1]);
    else staves.set(match[2], current);
  }
  return staves;
}

export const midiToFrequency = (midi: number) => 440 * 2 ** ((midi - 69) / 12);
