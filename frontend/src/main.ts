import { deleteExcerpt, getHealth, listExcerpts, type Excerpt, type Health } from "./api";
import { el } from "./ui/dom";
import { createExcerptView, type ExcerptView } from "./ui/excerpt";
import { renderEngineStatus, renderLibrary } from "./ui/library";
import { createUploadForm } from "./ui/upload";
import "./style.css";

const state = {
  excerpts: [] as Excerpt[],
  selectedId: null as string | null, // null shows the upload form
  health: null as Health | null,
  healthError: null as string | null,
  loadError: null as string | null,
};

const libraryHost = el("div");
const enginesHost = el("div");
const main = el("main", { class: "main" });
const newButton = el("button", { type: "button", class: "primary wide", textContent: "Upload excerpt" });
newButton.addEventListener("click", () => select(null));

document.querySelector<HTMLElement>("#app")!.append(
  el(
    "aside",
    { class: "sidebar" },
    el("div", { class: "brand", textContent: "Excerpt Player" }),
    newButton,
    el("h2", { textContent: "Library" }),
    libraryHost,
    enginesHost,
  ),
  main,
);

let openView: ExcerptView | null = null;
let openId: string | null = null;

function select(id: string | null): void {
  state.selectedId = id;
  render();
}

function render(): void {
  libraryHost.replaceChildren(
    state.loadError
      ? el("p", { class: "status error", textContent: state.loadError })
      : renderLibrary(state.excerpts, state.selectedId, select),
  );
  enginesHost.replaceChildren(renderEngineStatus(state.health, state.healthError));

  const selected = state.excerpts.find((e) => e.id === state.selectedId);
  if (selected && selected.id === openId) return; // keep the open score and its playback
  openView?.dispose();
  openView = null;
  openId = selected?.id ?? null;
  if (selected) {
    openView = createExcerptView(selected, {
      onDelete: remove,
      onChange: (updated) => {
        state.excerpts = state.excerpts.map((e) => (e.id === updated.id ? updated : e));
        render();
      },
    });
    main.replaceChildren(openView.element);
  } else {
    main.replaceChildren(
      el(
        "section",
        { class: "upload-pane" },
        el("h1", { textContent: "Upload an excerpt" }),
        createUploadForm(state.health, (excerpt) => {
          state.excerpts = [excerpt, ...state.excerpts];
          select(excerpt.id);
        }),
      ),
    );
  }
}

async function remove(excerpt: Excerpt): Promise<void> {
  try {
    await deleteExcerpt(excerpt.id);
  } catch (err) {
    alert(`Couldn't delete it: ${(err as Error).message}`);
    return;
  }
  state.excerpts = state.excerpts.filter((e) => e.id !== excerpt.id);
  select(null);
}

async function load(): Promise<void> {
  const [health, excerpts] = await Promise.allSettled([getHealth(), listExcerpts()]);
  if (health.status === "fulfilled") state.health = health.value;
  else state.healthError = (health.reason as Error).message;
  if (excerpts.status === "fulfilled") state.excerpts = excerpts.value;
  else state.loadError = (excerpts.reason as Error).message;
  render();
}

render();
void load();
