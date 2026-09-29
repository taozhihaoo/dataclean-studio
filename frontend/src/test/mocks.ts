/** Fetch-mocking helpers and shared API fixtures for tests. */

import { vi } from "vitest";
import type { JobDetail, PreviewResponse, ValidateResponse } from "../types";

type HandlerData = unknown;
type Handler = ((url: string, init: RequestInit | undefined) => HandlerData) | HandlerData;

export function installFetch(handlers: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    // longest matching pattern wins so /runs beats /:jobId
    const entry = Object.entries(handlers)
      .filter(([pattern]) => url.startsWith(pattern))
      .sort((a, b) => b[0].length - a[0].length)[0];
    if (!entry) {
      throw new Error(`Unhandled fetch in test: ${url}`);
    }
    const body = typeof entry[1] === "function" ? entry[1](url, init) : entry[1];
    if (body instanceof Response) {
      return body;
    }
    return new Response(JSON.stringify(body ?? {}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function errorResponse(status: number, code: string, message: string): Response {
  return new Response(JSON.stringify({ error: { code, message } }), { status });
}

export function installFetchError(status: number, body: unknown) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const jobDetail: JobDetail = {
  job_id: "abc12345",
  filename: "sample_customers.csv",
  source: "upload",
  status: "ready",
  row_count: 2,
  column_count: 3,
  created_at: "2026-09-30T10:00:00+00:00",
  updated_at: "2026-09-30T10:00:00+00:00",
  size_bytes: 120,
  is_transformed: false,
  columns: [
    { name: "cust_nm", detected_type: "string", null_count: 0, unique_count: 2, sample_values: ["John", "Jane"] },
    { name: "mail", detected_type: "email", null_count: 0, unique_count: 2, sample_values: ["j@x.com", "a@x.com"], invalid_count: 0 },
    { name: "age", detected_type: "integer", null_count: 1, unique_count: 2, sample_values: ["34", "28"] },
  ],
};

export const preview: PreviewResponse = {
  columns: ["cust_nm", "mail", "age"],
  rows: [
    { cust_nm: "John", mail: "j@x.com", age: "34" },
    { cust_nm: "Jane", mail: "a@x.com", age: null },
  ],
  total_rows: 2,
  limited: false,
};

export const validationOk: ValidateResponse = {
  total_rows: 2,
  error_count_total: 0,
  rows_dropped: 0,
  passed: true,
  output_rows: 2,
  rules: [
    {
      column: "mail",
      rule: "email",
      total_values: 2,
      error_count: 0,
      error_rate: 0,
      passed: true,
      samples: [],
    },
  ],
};

export const meta = {
  version: "1.0.0",
  max_upload_mb: 25,
  preview_row_limit: 50,
  inference: { default: "heuristic", available: ["heuristic"], openai_configured: false },
  target_schema_suggestions: ["customer_name", "email", "phone"],
};
