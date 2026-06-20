import type { components } from "./schema";

/** The §5 error envelope, shared by every non-2xx response and SSE `error` frames. */
export type ErrorBody = {
  code: string;
  message: string;
  detail?: unknown;
};

export class ApiError extends Error {
  code: string;
  detail: unknown;
  status: number;
  constructor(status: number, body: ErrorBody) {
    super(body.message || "Request failed.");
    this.name = "ApiError";
    this.code = body.code || "error";
    this.detail = body.detail ?? null;
    this.status = status;
  }
}

// Same-origin in prod (FastAPI serves the bundle); dev uses Vite's /api proxy.
const BASE = "";

type Params = Record<string, string | number | boolean | string[] | undefined | null>;

function buildQuery(params?: Params): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((item) => sp.append(k, String(item)));
    else sp.append(k, String(v));
  }
  const q = sp.toString();
  return q ? `?${q}` : "";
}

async function parseError(res: Response): Promise<never> {
  let body: ErrorBody = { code: "error", message: res.statusText };
  try {
    const json = await res.json();
    if (json?.error) body = json.error as ErrorBody;
  } catch {
    /* non-JSON error body — keep the status text */
  }
  throw new ApiError(res.status, body);
}

async function request<T>(
  method: string,
  path: string,
  opts: { params?: Params; body?: unknown } = {},
): Promise<T> {
  const res = await fetch(BASE + path + buildQuery(opts.params), {
    method,
    headers: opts.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const client = {
  get: <T>(path: string, params?: Params) => request<T>("GET", path, { params }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

// --------------------------------------------------------------------------- //
// SSE — one helper, two consumers (chat tokens, task progress). §4.
// Parses `data:` frames out of a fetch ReadableStream and yields the JSON.
// Use POST for chat (EventSource can't send a body); GET for task progress.
// --------------------------------------------------------------------------- //

export type TaskFrame =
  | { type: "progress"; task: components["schemas"]["Task"] }
  | { type: "complete"; task: components["schemas"]["Task"] }
  | { type: "failed"; task: components["schemas"]["Task"] }
  | { type: "error"; error: ErrorBody };

async function* sseRaw(
  path: string,
  init?: RequestInit,
): AsyncGenerator<unknown> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) await parseError(res);
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let sep: number;
    // Frames are separated by a blank line (\n\n).
    while ((sep = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      for (const line of frame.split("\n")) {
        const trimmed = line.startsWith("data:") ? line.slice(5).trim() : "";
        if (trimmed) yield JSON.parse(trimmed);
      }
    }
  }
}

export function taskStream(
  taskId: string,
  signal?: AbortSignal,
): AsyncGenerator<TaskFrame> {
  return sseRaw(`/api/tasks/${taskId}/stream`, { signal }) as AsyncGenerator<TaskFrame>;
}
