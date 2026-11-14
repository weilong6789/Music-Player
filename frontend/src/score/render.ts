import type { VerovioToolkit } from "verovio/esm";
import type { TimemapEntry } from "../playback/timeline";

let toolkitClass: Promise<{ module: unknown; Toolkit: typeof VerovioToolkit }> | null = null;

/** Verovio is several MB of WASM, so it's only fetched when a score is first opened. */
function loadVerovio() {
  toolkitClass ??= Promise.all([import("verovio/wasm"), import("verovio/esm")]).then(
    async ([wasm, esm]) => ({ module: await wasm.default(), Toolkit: esm.VerovioToolkit }),
  );
  return toolkitClass;
}

const SCALE = 35;

/** A loaded score: renders into a host element and answers timing/pitch questions. */
export class ScoreView {
  private width = 0;

  private constructor(
    private readonly toolkit: VerovioToolkit,
    private readonly host: HTMLElement,
  ) {}

  static async create(host: HTMLElement, musicxml: string): Promise<ScoreView> {
    const { module, Toolkit } = await loadVerovio();
    const toolkit = new Toolkit(module as ConstructorParameters<typeof VerovioToolkit>[0]);
    toolkit.setOptions({
      scale: SCALE,
      breaks: "auto",
      adjustPageHeight: true,
      pageHeight: 60000,
      header: "none",
      footer: "none",
      pageMarginTop: 60,
      pageMarginBottom: 60,
      pageMarginLeft: 60,
      pageMarginRight: 60,
    });
    if (!toolkit.loadData(musicxml)) throw new Error("Verovio couldn't read the score");
    const view = new ScoreView(toolkit, host);
    view.layout();
    return view;
  }

  /** Re-flow the systems to the host's current width. Element ids stay the same. */
  layout(): void {
    const width = Math.max(320, Math.floor(this.host.clientWidth));
    if (width === this.width) return;
    this.width = width;
    this.toolkit.setOptions({ pageWidth: Math.round((width * 100) / SCALE) });
    this.toolkit.redoLayout();
    const pages: string[] = [];
    for (let page = 1; page <= this.toolkit.getPageCount(); page++) {
      pages.push(this.toolkit.renderToSVG(page));
    }
    this.host.innerHTML = pages.join("");
  }

  timemap(): TimemapEntry[] {
    return this.toolkit.renderToTimemap() as unknown as TimemapEntry[];
  }

  mei(): string {
    return this.toolkit.getMEI();
  }

  midiOf(id: string): number | undefined {
    const pitch = this.toolkit.getMIDIValuesForElement(id)?.pitch;
    return typeof pitch === "number" && pitch > 0 ? pitch : undefined;
  }

  element(id: string): Element | null {
    return this.host.querySelector(`[id="${CSS.escape(id)}"]`);
  }

  dispose(): void {
    this.toolkit.destroy();
    this.host.replaceChildren();
  }
}
