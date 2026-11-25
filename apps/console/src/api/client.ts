import type {
  Health,
  Job,
  JobEvent,
  Lanes,
  LibraryStats,
  LibraryTrack,
  MixScriptCreate,
  MixScriptDocument,
  MixScriptVersion,
  PairRequest,
  Peaks,
  PlanRequest,
  ProjectInfo,
  RenderRecord,
  SystemInfo,
  TrackRecord,
} from "@mixconsole/schema-ts";

/** Typed client for the local server. Every call carries the per-run token; nothing leaves 127.0.0.1. */

const BASE = "/api/v1";
const TOKEN_KEY = "mixconsole.token";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function initToken(): string | null {
  try {
    const url = new URL(window.location.href);
    const fromUrl = url.searchParams.get("token");
    if (fromUrl) {
      sessionStorage.setItem(TOKEN_KEY, fromUrl);
      url.searchParams.delete("token");
      window.history.replaceState(null, "", url.pathname + url.search + url.hash);
      return fromUrl;
    }
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function token(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(value: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, value);
  } catch {
    /* private mode: the token then lives for this load only through initToken() */
  }
}

/** URL for <audio>, EventSource and downloads, which cannot send an Authorization header. */
export function withToken(path: string): string {
  return `${path}${path.includes("?") ? "&" : "?"}token=${encodeURIComponent(token())}`;
}

async function failure(response: Response): Promise<ApiError> {
  let message = `${response.status} ${response.statusText}`;
  try {
    const body: unknown = await response.json();
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") message = detail;
    else if (Array.isArray(detail) && detail[0]?.msg) message = String(detail[0].msg);
  } catch {
    /* keep the status text */
  }
  return new ApiError(response.status, message);
}

async function call<T>(
  method: string,
  path: string,
  body?: unknown,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token()}`);
  let payload: BodyInit | undefined;
  if (body instanceof Blob) {
    payload = body;
    headers.set("Content-Type", "application/octet-stream");
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${BASE}${path}`, { ...init, method, headers, body: payload });
  if (!response.ok) throw await failure(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const enc = encodeURIComponent;
const projectPath = (id: string) => `/projects/${enc(id)}`;

export const api = {
  health: () => fetch(`${BASE}/health`).then((r) => r.json() as Promise<Health>),
  system: () => call<SystemInfo>("GET", "/system"),
  projects: () => call<ProjectInfo[]>("GET", "/projects"),
  createProject: (name: string) => call<ProjectInfo>("POST", "/projects", { name }),
  tracks: (project: string) => call<TrackRecord[]>("GET", `${projectPath(project)}/tracks`),
  addTracks: (project: string, paths: string[]) =>
    call<TrackRecord[]>("POST", `${projectPath(project)}/tracks`, { paths }),
  upload: (project: string, file: File) =>
    call<TrackRecord>("POST", `${projectPath(project)}/uploads?name=${enc(file.name)}`, file),
  analyze: (project: string, hashes: string[]) =>
    call<Job>("POST", `${projectPath(project)}/analyses`, { hashes }),
  lanes: (project: string, hash: string) =>
    call<Lanes>("GET", `${projectPath(project)}/tracks/${hash}/lanes`),
  waveform: (project: string, hash: string, resolution = 1024) =>
    call<Peaks>("GET", `${projectPath(project)}/tracks/${hash}/waveform?resolution=${resolution}`),
  previewUrl: (project: string, hash: string) =>
    withToken(`${BASE}${projectPath(project)}/tracks/${hash}/preview`),
  plan: (project: string, body: PlanRequest) =>
    call<Job>("POST", `${projectPath(project)}/plans`, body),
  mix: (project: string, body: PairRequest) =>
    call<Job>("POST", `${projectPath(project)}/mixes`, body),
  render: (project: string, mixscriptId: string, format: "wav" | "flac" = "wav") =>
    call<Job>("POST", `${projectPath(project)}/renders`, { mixscript_id: mixscriptId, format }),
  mixscripts: (project: string) =>
    call<MixScriptVersion[]>("GET", `${projectPath(project)}/mixscripts`),
  mixscript: (project: string, id: string) =>
    call<MixScriptDocument>("GET", `${projectPath(project)}/mixscripts/${enc(id)}`),
  addMixscript: (project: string, body: MixScriptCreate) =>
    call<MixScriptVersion>("POST", `${projectPath(project)}/mixscripts`, body),
  renders: (project: string) => call<RenderRecord[]>("GET", `${projectPath(project)}/renders`),
  renderRecord: (project: string, id: string) =>
    call<RenderRecord>("GET", `${projectPath(project)}/renders/${id}`),
  renderFileUrl: (project: string, id: string, name: string) =>
    withToken(`${BASE}${projectPath(project)}/renders/${id}/files/${enc(name)}`),
  renderFileJson: (project: string, id: string, name: string): Promise<unknown> =>
    call<unknown>("GET", `${projectPath(project)}/renders/${id}/files/${enc(name)}`),
  library: (params: {
    q?: string;
    bpm_min?: number;
    bpm_max?: number;
    camelot?: string;
    limit?: number;
  }) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") query.set(key, String(value));
    }
    return call<LibraryTrack[]>("GET", `/library/tracks?${query}`);
  },
  libraryStats: () => call<LibraryStats>("GET", "/library/stats"),
  scan: (directory: string) => call<Job>("POST", "/library/scans", { directory }),
  job: (id: string) => call<Job>("GET", `/jobs/${enc(id)}`),
  cancel: (id: string) => call<Job>("POST", `/jobs/${enc(id)}/cancel`),
  history: (id: string, after = 0) =>
    call<JobEvent[]>("GET", `/jobs/${enc(id)}/history?after=${after}`),
};

export const TERMINAL: Job["state"][] = ["done", "failed", "cancelled"];

/**
 * Follow a job to its end. Uses Server-Sent Events (token in the query) and falls back to polling
 * the stored history if the stream cannot be opened.
 */
export function followJob(id: string, onProgress: (event: JobEvent) => void): Promise<Job> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (job: Job) => {
      if (settled) return;
      settled = true;
      source?.close();
      resolve(job);
    };
    const poll = async () => {
      let after = 0;
      while (!settled) {
        try {
          for (const event of await api.history(id, after)) {
            after = event.seq;
            onProgress(event);
          }
          const job = await api.job(id);
          if (TERMINAL.includes(job.state)) return finish(job);
        } catch (error) {
          settled = true;
          return reject(error);
        }
        await new Promise((r) => setTimeout(r, 400));
      }
    };
    let source: EventSource | null = null;
    if (typeof EventSource === "undefined") {
      void poll();
      return;
    }
    source = new EventSource(withToken(`${BASE}/jobs/${enc(id)}/events`));
    source.addEventListener("progress", (message) => {
      onProgress(JSON.parse((message as MessageEvent<string>).data) as JobEvent);
    });
    source.addEventListener("end", (message) => {
      finish(JSON.parse((message as MessageEvent<string>).data) as Job);
    });
    source.onerror = () => {
      if (settled || source?.readyState === EventSource.CONNECTING) return;
      source?.close();
      void poll();
    };
  });
}
