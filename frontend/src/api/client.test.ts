import { describe, expect, it, vi } from "vitest";
import { ApiError, api, downloadFile, request } from "./client";

describe("api client", () => {
  it("parses JSON responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }))
    );
    const body = await api.get<{ ok: boolean }>("/api/x");
    expect(body.ok).toBe(true);
  });

  it("throws ApiError with server code and message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ error: { code: "job_not_found", message: "Job was not found." } }),
            { status: 404 }
          )
      )
    );
    const error = await api.get("/api/jobs/nope").catch((err) => err);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("job_not_found");
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).message).toBe("Job was not found.");
  });

  it("falls back to a generic message for non-JSON errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500 })));
    const error = await api.get("/api/x").catch((err) => err);
    expect((error as ApiError).code).toBe("http_error");
  });

  it("posts JSON bodies with the right content type", async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response(JSON.stringify({ received: true }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);
    await api.post("/api/x", { a: 1 });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ a: 1 }));
  });

  it("sends FormData uploads without a JSON content type", async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response(JSON.stringify({}), { status: 201 })
    );
    vi.stubGlobal("fetch", fetchMock);
    const form = new FormData();
    form.append("upload", new File(["x"], "t.csv"));
    await request("/api/files/upload", { method: "POST", body: form });
    const headers = (fetchMock.mock.calls[0][1] as RequestInit).headers as
      | Record<string, string>
      | undefined;
    expect(headers?.["Content-Type"]).toBeUndefined();
  });
});

describe("downloadFile", () => {
  it("triggers a browser download with the server filename", async () => {
    const disposition = 'attachment; filename="clean.csv"';
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("a,b\n1,2\n", { status: 200, headers: { "Content-Disposition": disposition } }))
    );
    const clicks: string[] = [];
    const anchorSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicks.push(this.download);
      });
    URL.createObjectURL = vi.fn(() => "blob:fake");
    URL.revokeObjectURL = vi.fn();
    await downloadFile("/api/export", { method: "POST" });
    expect(clicks).toEqual(["clean.csv"]);
    anchorSpy.mockRestore();
  });
});
