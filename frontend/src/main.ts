import { getHealth, type EngineStatus } from "./api";
import "./style.css";

const ENGINE_LABELS: Record<string, string> = {
  audiveris: "Audiveris",
  homr: "homr",
};

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function engineRow(name: string, status: EngineStatus): HTMLElement {
  const row = el("li", `engine ${status.available ? "ok" : "missing"}`);
  const head = el("div", "engine-head");
  head.append(
    el("span", "dot"),
    el("span", "engine-name", ENGINE_LABELS[name] ?? name),
    el("span", "engine-state", status.available ? "Installed" : "Not installed"),
  );
  row.append(head, el("p", "engine-detail", status.detail));
  return row;
}

async function render(): Promise<void> {
  const app = document.querySelector<HTMLElement>("#app")!;
  const status = el("section", "card");
  status.append(el("h2", undefined, "OMR engines"));
  app.replaceChildren(el("h1", undefined, "Excerpt Player"), status);

  try {
    const health = await getHealth();
    const list = el("ul", "engines");
    for (const [name, engine] of Object.entries(health.engines)) {
      list.append(engineRow(name, engine));
    }
    status.append(list);
  } catch (err) {
    status.append(el("p", "error", `Can't reach the backend: ${(err as Error).message}`));
  }
}

void render();
