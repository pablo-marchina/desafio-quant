export type JsonObject = Record<string, unknown>;

export interface RequestOptions extends RequestInit {
  /** Maximum request duration. Use 0 to disable the timeout. */
  timeoutMs?: number;
  /** Reuse an identical in-flight GET request. */
  dedupe?: boolean;
}

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

const DEFAULT_READ_TIMEOUT_MS = 30_000;
const DEFAULT_WRITE_TIMEOUT_MS = 10 * 60_000;
const inFlightGetRequests = new Map<string, Promise<unknown>>();

function requestKey(url: string, method: string): string {
  return `${method}:${url}`;
}

function defaultTimeoutMs(method: string): number {
  return method === "GET" || method === "HEAD"
    ? DEFAULT_READ_TIMEOUT_MS
    : DEFAULT_WRITE_TIMEOUT_MS;
}

async function executeRequest<T>(
  url: string,
  options: RequestOptions,
): Promise<T> {
  const {
    timeoutMs: requestedTimeoutMs,
    dedupe: _dedupe,
    signal: callerSignal,
    headers: callerHeaders,
    ...fetchInit
  } = options;
  const method = (fetchInit.method || "GET").toUpperCase();
  const timeoutMs = requestedTimeoutMs ?? defaultTimeoutMs(method);
  const controller = new AbortController();
  let timedOut = false;

  const abortFromCaller = () => controller.abort(callerSignal?.reason);
  if (callerSignal?.aborted) {
    abortFromCaller();
  } else {
    callerSignal?.addEventListener("abort", abortFromCaller, { once: true });
  }

  const timeoutId = timeoutMs > 0
    ? window.setTimeout(() => {
        timedOut = true;
        controller.abort(new DOMException("Request timed out", "TimeoutError"));
      }, timeoutMs)
    : null;

  const headers = new Headers(callerHeaders);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });
  } catch (error) {
    if (timedOut) {
      throw new Error(`API request timed out after ${Math.round(timeoutMs / 1000)}s: ${url}`);
    }
    if (callerSignal?.aborted) {
      throw new Error(`API request cancelled: ${url}`);
    }
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`API offline or unreachable at ${API_BASE_URL}: ${detail}`);
  } finally {
    if (timeoutId !== null) window.clearTimeout(timeoutId);
    callerSignal?.removeEventListener("abort", abortFromCaller);
  }

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : String(body);
    throw new Error(`API request failed (${response.status}): ${detail}`);
  }

  return body as T;
}

export function requestJson<T>(
  path: string,
  init: RequestOptions = {},
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const method = (init.method || "GET").toUpperCase();
  const shouldDedupe =
    (init.dedupe ?? true) &&
    method === "GET" &&
    !init.body &&
    !init.signal;

  if (!shouldDedupe) {
    return executeRequest<T>(url, init);
  }

  const key = requestKey(url, method);
  const existing = inFlightGetRequests.get(key);
  if (existing) return existing as Promise<T>;

  const request = executeRequest<T>(url, init).finally(() => {
    inFlightGetRequests.delete(key);
  });
  inFlightGetRequests.set(key, request);
  return request;
}
