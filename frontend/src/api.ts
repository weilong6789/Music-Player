export interface EngineStatus {
  available: boolean;
  detail: string;
}

export interface Health {
  status: string;
  engines: Record<string, EngineStatus>;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json() as Promise<T>;
}

export const getHealth = () => getJson<Health>("/api/health");
