import type { Excerpt, Health } from "../api";
import { el } from "./dom";

const ENGINE_NAMES: Record<string, string> = { audiveris: "Audiveris", homr: "homr" };

export function renderLibrary(
  excerpts: Excerpt[],
  selectedId: string | null,
  onSelect: (id: string) => void,
): HTMLElement {
  if (excerpts.length === 0) {
    return el("p", { class: "empty", textContent: "No excerpts yet." });
  }
  const list = el("ul", { class: "library" });
  for (const excerpt of excerpts) {
    const button = el(
      "button",
      { type: "button", class: excerpt.id === selectedId ? "item selected" : "item" },
      el("span", { class: "item-title", textContent: excerpt.title }),
      el("span", {
        class: "item-sub",
        textContent: `${excerpt.measure_count} bars · ${new Date(excerpt.created).toLocaleDateString()}`,
      }),
    );
    if (excerpt.id === selectedId) button.setAttribute("aria-current", "true");
    button.addEventListener("click", () => onSelect(excerpt.id));
    list.append(el("li", {}, button));
  }
  return list;
}

export function renderEngineStatus(health: Health | null, error: string | null): HTMLElement {
  const box = el("div", { class: "engines" }, el("h2", { textContent: "OMR engines" }));
  if (!health) {
    box.append(el("p", { class: "status error", textContent: error ?? "Checking…" }));
    return box;
  }
  for (const [name, engine] of Object.entries(health.engines)) {
    box.append(
      el(
        "div",
        { class: engine.available ? "engine ok" : "engine missing", title: engine.detail },
        el("span", { class: "dot" }),
        el("span", { textContent: ENGINE_NAMES[name] ?? name }),
        el("span", { class: "engine-state", textContent: engine.available ? "Installed" : "Not installed" }),
      ),
    );
    if (!engine.available) box.append(el("p", { class: "engine-detail", textContent: engine.detail }));
  }
  return box;
}
