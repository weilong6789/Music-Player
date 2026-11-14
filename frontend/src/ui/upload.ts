import {
  uploadExcerpt,
  type AccidentalRule,
  type CleanupFlags,
  type EngineChoice,
  type Excerpt,
  type Health,
} from "../api";
import { el } from "./dom";

const ENGINE_LABELS: Record<EngineChoice, string> = {
  auto: "Auto (Audiveris for PDFs, homr for photos)",
  audiveris: "Audiveris",
  homr: "homr",
};

const CLEANUP_LABELS: Record<keyof CleanupFlags, string> = {
  perspective: "Flatten a photographed page",
  deskew: "Straighten tilted staves",
  threshold: "Black-and-white threshold",
};

const isPdf = (file: File) => file.name.toLowerCase().endsWith(".pdf");

export function createUploadForm(health: Health | null, onDone: (excerpt: Excerpt) => void): HTMLElement {
  const file = el("input", { type: "file", accept: ".pdf,.png,.jpg,.jpeg", required: true });

  const engine = el("select");
  for (const choice of Object.keys(ENGINE_LABELS) as EngineChoice[]) {
    const installed = choice === "auto" || (health?.engines[choice]?.available ?? true);
    engine.append(
      el("option", {
        value: choice,
        textContent: ENGINE_LABELS[choice] + (installed ? "" : " (not installed)"),
        disabled: !installed,
      }),
    );
  }

  const rule = el(
    "select",
    {},
    el("option", { value: "bar", textContent: "Carry through the bar (traditional)" }),
    el("option", { value: "note", textContent: "Apply only to their own note" }),
  );

  const cleanupBoxes = {} as Record<keyof CleanupFlags, HTMLInputElement>;
  const cleanup = el("fieldset", { class: "cleanup" }, el("legend", { textContent: "Image cleanup" }));
  for (const name of Object.keys(CLEANUP_LABELS) as (keyof CleanupFlags)[]) {
    cleanupBoxes[name] = el("input", { type: "checkbox" });
    cleanup.append(el("label", { class: "check" }, cleanupBoxes[name], CLEANUP_LABELS[name]));
  }
  const applyCleanupDefaults = () => {
    // Clean PDFs are left alone; photos get straightened.
    const photo = file.files?.[0] ? !isPdf(file.files[0]) : false;
    cleanupBoxes.perspective.checked = photo;
    cleanupBoxes.deskew.checked = photo;
    cleanupBoxes.threshold.checked = false;
  };
  file.addEventListener("change", applyCleanupDefaults);

  const submit = el("button", { type: "submit", class: "primary", textContent: "Read the music" });
  const status = el("p", { class: "status", hidden: true });
  status.setAttribute("role", "status");

  const form = el(
    "form",
    { class: "upload" },
    el("label", {}, "Scan or photo (PDF, PNG, JPG)", file),
    el("label", {}, "OMR engine", engine),
    el("label", {}, "Accidentals", rule),
    cleanup,
    submit,
    status,
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const chosen = file.files?.[0];
    if (!chosen) return;

    submit.disabled = true;
    status.hidden = false;
    status.className = "status busy";
    status.textContent = "Reading the music. This can take up to a minute.";
    try {
      const excerpt = await uploadExcerpt({
        file: chosen,
        engine: engine.value as EngineChoice,
        accidentalRule: rule.value as AccidentalRule,
        cleanup: {
          perspective: cleanupBoxes.perspective.checked,
          deskew: cleanupBoxes.deskew.checked,
          threshold: cleanupBoxes.threshold.checked,
        },
      });
      form.reset();
      applyCleanupDefaults();
      status.hidden = true;
      onDone(excerpt);
    } catch (err) {
      status.className = "status error";
      status.textContent = (err as Error).message;
    } finally {
      submit.disabled = false;
    }
  });

  return form;
}
