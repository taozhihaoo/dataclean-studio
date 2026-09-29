/** Thin fetch wrapper: JSON in/out, blob downloads, uniform ApiError. */

import type { ApiErrorBody, BatchUploadResponse } from "../types";

export class ApiError extends Error {
  code: string;
  status: number;
  details?: Record<string, unknown> | null;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown> | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const DEFAULT_TIMEOUT_MS = 60_000;
const UPLOAD_TIMEOUT_MS = 120_000;

async function parseError(response: Response): Promise<ApiError> {
  let code = "http_error";
  let message = `Request failed with status ${response.status}`;
  let details: Record<string, unknown> | null = null;
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body?.error) {
      code = body.error.code;
      message = body.error.message;
      details = body.error.details ?? null;
    }
  } catch {
    // non-JSON error body: keep defaults
  }
  return new ApiError(response.status, code, message, details);
}

async function requestRaw<T>(path: string, options: RequestInit, timeoutMs: number): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(path, { ...options, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "timeout", "The request timed out. Please try again.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers =
    options.body instanceof FormData
      ? options.headers
      : { "Content-Type": "application/json", ...options.headers };
  return requestRaw<T>(path, { headers, ...options }, DEFAULT_TIMEOUT_MS);
}

export async function downloadFile(path: string, options: RequestInit = {}): Promise<void> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  const filename = match ? decodeURIComponent(match[1]) : "download";
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function uploadFile<T>(file: File): Promise<T> {
  const form = new FormData();
  form.append("upload", file);
  return requestRaw<T>(
    "/api/files/upload",
    { method: "POST", body: form },
    UPLOAD_TIMEOUT_MS
  );
}

/** Upload several files in one request; each file is processed independently
 * by the backend, so per-file failures come back as results, not errors. */
export function uploadFilesBatch(files: File[]): Promise<BatchUploadResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  return requestRaw<BatchUploadResponse>(
    "/api/files/upload-batch",
    { method: "POST", body: form },
    UPLOAD_TIMEOUT_MS
  );
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: uploadFile,
  uploadBatch: uploadFilesBatch,
  download: downloadFile,
};
