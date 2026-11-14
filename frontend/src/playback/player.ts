import * as Tone from "tone";
import type { Sound } from "./sounds";
import type { Timeline } from "./timeline";

export type PlayerState = "stopped" | "playing" | "paused";

export interface PlayerCallbacks {
  /** A notehead starts or stops sounding. Called in sync with the audio. */
  onMark(id: string, on: boolean): void;
  onState(state: PlayerState): void;
}

/**
 * Schedules a timeline on Tone's transport. Timeline times are multiplied by `scale`,
 * so the transport runs in real seconds and the score position is seconds / scale.
 */
export class Player {
  private state: PlayerState = "stopped";
  private scale = 1;
  private lit = new Set<string>();
  private readonly transport = Tone.getTransport();

  constructor(
    private timeline: Timeline,
    private sound: Sound,
    private readonly callbacks: PlayerCallbacks,
  ) {}

  getState(): PlayerState {
    return this.state;
  }

  setSound(sound: Sound): void {
    this.sound.releaseAll();
    this.sound = sound;
  }

  /** Change speed. During playback this carries on from the same place in the score. */
  setScale(scale: number): void {
    if (scale === this.scale) return;
    const positionMs = this.positionMs();
    this.scale = scale;
    if (this.state === "stopped") return;
    this.schedule(positionMs);
    this.transport.seconds = (positionMs * scale) / 1000;
  }

  async play(): Promise<void> {
    if (this.state === "playing") return;
    await Tone.start();
    if (this.state === "stopped") {
      this.transport.seconds = 0;
      this.schedule(0);
    }
    this.transport.start();
    this.setState("playing");
  }

  pause(): void {
    if (this.state !== "playing") return;
    this.transport.pause();
    this.sound.releaseAll();
    this.setState("paused");
  }

  stop(): void {
    this.transport.stop();
    this.transport.cancel(0);
    this.sound.releaseAll();
    this.clearMarks();
    if (this.state !== "stopped") this.setState("stopped");
  }

  dispose(): void {
    this.stop();
  }

  private positionMs(): number {
    return this.state === "stopped" ? 0 : (this.transport.seconds * 1000) / this.scale;
  }

  private schedule(fromMs: number): void {
    const { transport, scale } = this;
    const draw = Tone.getDraw();
    const seconds = (ms: number) => (ms * scale) / 1000;

    transport.cancel(0);
    this.sound.releaseAll();
    this.clearMarks();

    for (const note of this.timeline.notes) {
      if (note.startMs < fromMs) continue;
      const duration = Math.max(0.03, seconds(note.endMs - note.startMs));
      transport.schedule((time) => this.sound.play(note.midi, duration, time), seconds(note.startMs));
    }

    for (const mark of this.timeline.marks) {
      if (mark.endMs <= fromMs) continue;
      if (mark.startMs < fromMs) {
        this.mark(mark.id, true); // already sounding at the resume point
      } else {
        transport.schedule(
          (time) => draw.schedule(() => this.mark(mark.id, true), time),
          seconds(mark.startMs),
        );
      }
      transport.schedule(
        (time) => draw.schedule(() => this.mark(mark.id, false), time),
        seconds(mark.endMs),
      );
    }

    // Let the last note ring out before resetting.
    transport.schedule(
      (time) => draw.schedule(() => this.stop(), time),
      seconds(this.timeline.durationMs) + 0.2,
    );
  }

  private mark(id: string, on: boolean): void {
    if (on) this.lit.add(id);
    else this.lit.delete(id);
    this.callbacks.onMark(id, on);
  }

  private clearMarks(): void {
    for (const id of [...this.lit]) this.mark(id, false);
  }

  private setState(state: PlayerState): void {
    this.state = state;
    this.callbacks.onState(state);
  }
}
