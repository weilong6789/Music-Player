export interface EngineStatus {
  available: boolean;
  detail: string;
}

export interface Health {
  status: string;
  engines: Record<string, EngineStatus>;
}

export type EngineChoice = "auto" | "audiveris" | "homr";
export type AccidentalRule = "bar" | "note";

export interface CleanupFlags {
  perspective: boolean;
  deskew: boolean;
  threshold: boolean;
}

export interface Excerpt {
  id: string;
  title: string;
  original_filename: string;
  source_type: "pdf" | "image";
  created: string;
  page_count: number;
  engine_requested: EngineChoice;
  engine: string;
  accidental_rule: AccidentalRule;
  cleanup: CleanupFlags;
  cleanup_applied: string[];
  tempo_bpm: number;
  tempo_beat: number;
  tempo_source: "marking" | "text" | "default";
  parts: { index: number; name: string }[];
  playback_part: number;
  measure_count: number;
  note_count: number;
  warnings: string[];
}

export interface UploadOptions {
  file: File;
  engine: EngineChoice;
  accidentalRule: AccidentalRule;
  cleanup: CleanupFlags;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new Error("Can't reach the backend. Is the server still running?");
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // not JSON; keep the status line
    }
    throw new Error(message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const getHealth = () => request<Health>("/api/health");
export const listExcerpts = () => request<Excerpt[]>("/api/excerpts");
export const deleteExcerpt = (id: string) =>
  request<void>(`/api/excerpts/${id}`, { method: "DELETE" });

export function uploadExcerpt(options: UploadOptions): Promise<Excerpt> {
  const form = new FormData();
  form.append("file", options.file);
  form.append("engine", options.engine);
  form.append("accidental_rule", options.accidentalRule);
  for (const [name, value] of Object.entries(options.cleanup)) {
    form.append(name, String(value));
  }
  return request<Excerpt>("/api/excerpts", { method: "POST", body: form });
}

export const pageUrl = (id: string, page: number) => `/api/excerpts/${id}/pages/${page}`;
export const scoreUrl = (id: string) => `/api/excerpts/${id}/score?format=musicxml`;
