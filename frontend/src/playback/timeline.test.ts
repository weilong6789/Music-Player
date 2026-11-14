import fixture from "../fixtures/violin-72.musicxml?raw";
import createVerovioModule from "verovio/wasm";
import { VerovioToolkit } from "verovio/esm";
import { beforeAll, describe, expect, it } from "vitest";
import {
  buildTimeline,
  midiToFrequency,
  noteStaves,
  openingQpm,
  tieTargets,
  timeScale,
  type TimemapEntry,
  type Timeline,
} from "./timeline";

// Four bars of 4/4 at ♩ = 72:
// G4 F#4 F#4 A4 | Bb4 C5 Bb4 D5 | E5(half) C#5(half)~ | ~C#5(half) D5(half)
const QUARTER_MS = 60000 / 72;

let verovioModule: Awaited<ReturnType<typeof createVerovioModule>>;
let toolkit: VerovioToolkit;
let timemap: TimemapEntry[];
let timeline: Timeline;

beforeAll(async () => {
  verovioModule = await createVerovioModule();
  toolkit = new VerovioToolkit(verovioModule);
  toolkit.loadData(fixture);
  timemap = toolkit.renderToTimemap() as unknown as TimemapEntry[];
  timeline = buildTimeline(timemap, (id) => toolkit.getMIDIValuesForElement(id).pitch, toolkit.getMEI());
});

describe("timeline from the fixture", () => {
  it("has the right pitches in order", () => {
    expect(timeline.notes.map((n) => n.midi)).toEqual([67, 66, 66, 69, 70, 72, 70, 74, 76, 73, 74]);
  });

  it("starts each note on its beat at the marked tempo", () => {
    const beats = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 14];
    timeline.notes.forEach((note, i) => expect(note.startMs).toBeCloseTo(beats[i] * QUARTER_MS, -1));
    expect(timeline.durationMs).toBeCloseTo(16 * QUARTER_MS, -1);
    expect(timeline.baseQpm).toBe(72);
  });

  it("sounds a tied note once for its whole length", () => {
    const tied = timeline.notes[9];
    expect(tied.midi).toBe(73);
    expect(tied.endMs - tied.startMs).toBeCloseTo(4 * QUARTER_MS, -1);
  });

  it("still marks both noteheads of a tie", () => {
    expect(timeline.marks).toHaveLength(12);
    const second = timeline.marks[10];
    expect(second.startMs).toBeCloseTo(12 * QUARTER_MS, -1);
    expect(timeline.notes.some((n) => n.id === second.id)).toBe(false);
  });

  it("gives every note a length", () => {
    for (const note of timeline.notes) expect(note.endMs).toBeGreaterThan(note.startMs);
  });
});

describe("tempo", () => {
  const lengthAt = (percent: number, targetQpm = 72) =>
    timeline.durationMs * timeScale(timeline.baseQpm, targetQpm, percent);

  it("plays at the marked tempo at 100%", () => {
    expect(lengthAt(100)).toBeCloseTo(timeline.durationMs, 0);
  });

  it("halves the duration when the percentage doubles", () => {
    expect(lengthAt(100) / lengthAt(50)).toBeCloseTo(0.5, 6);
    expect(lengthAt(150) / lengthAt(75)).toBeCloseTo(0.5, 6);
  });

  it("follows a tempo typed in over the marked one", () => {
    expect(lengthAt(100, 144)).toBeCloseTo(timeline.durationMs / 2, 0);
  });

  it("gets a dotted-quarter marking right", () => {
    const xml = fixture.replace(
      /<metronome[^>]*>[\s\S]*?<\/metronome>/,
      "<metronome><beat-unit>quarter</beat-unit><beat-unit-dot/><per-minute>60</per-minute></metronome>",
    ).replace(/<sound tempo="[^"]*"\s*\/>/, "");
    expect(xml).toContain("beat-unit-dot");
    const dotted = new VerovioToolkit(verovioModule);
    dotted.loadData(xml);
    const map = dotted.renderToTimemap() as unknown as TimemapEntry[];
    dotted.destroy();
    // Whatever tempo Verovio timed it at, scaling to ♩. = 60 (90 quarters a minute)
    // has to land a quarter note on 667 ms.
    const quarterMs = map.find((e) => e.qstamp === 1)!.tstamp;
    expect(quarterMs * timeScale(openingQpm(map), 60 * 1.5, 100)).toBeCloseTo(60000 / 90, 0);
  });

  it("uses Verovio's default when the score has no tempo", () => {
    const bare = new VerovioToolkit(verovioModule);
    bare.loadData(fixture.replace(/<direction[\s\S]*?<\/direction>/g, ""));
    expect(openingQpm(bare.renderToTimemap() as unknown as TimemapEntry[])).toBe(120);
    bare.destroy();
    expect(openingQpm([])).toBe(120);
    expect(timeScale(120, 80, 100)).toBe(1.5); // an 80 BPM placeholder slows a 120 timemap down
  });
});

describe("staff filter", () => {
  const mei = `
    <staffDef n="1"/><staffDef n="2"/>
    <staff n="1"><note xml:id="a" pname="g"/><note xml:id="b" pname="a"/></staff>
    <staff n="2"><note pname="c" xml:id="c"/></staff>
    <tie startid="#a" endid="#b"/>`;
  const map: TimemapEntry[] = [
    { tstamp: 0, qstamp: 0, on: ["a", "c"] },
    { tstamp: 500, qstamp: 1, off: ["a"], on: ["b"] },
    { tstamp: 1000, qstamp: 2, off: ["b", "c"] },
  ];
  const midi = (id: string) => ({ a: 67, b: 67, c: 48 })[id];

  it("reads staves and ties from the MEI", () => {
    expect([...noteStaves(mei)]).toEqual([["a", 1], ["b", 1], ["c", 2]]);
    expect([...tieTargets(mei)]).toEqual([["a", "b"]]);
  });

  it("plays only the chosen staff", () => {
    expect(buildTimeline(map, midi, mei, 2).notes).toEqual([{ id: "c", startMs: 0, endMs: 1000, midi: 48 }]);
    expect(buildTimeline(map, midi, mei, 1).notes).toEqual([{ id: "a", startMs: 0, endMs: 1000, midi: 67 }]);
  });

  it("plays everything when the staff doesn't exist", () => {
    expect(buildTimeline(map, midi, mei, 5).notes.map((n) => n.id)).toEqual(["a", "c"]);
  });
});

it("converts MIDI numbers to equal-tempered frequencies", () => {
  expect(midiToFrequency(69)).toBe(440);
  expect(midiToFrequency(57)).toBeCloseTo(220, 9);
  expect(midiToFrequency(60)).toBeCloseTo(261.626, 3);
});
