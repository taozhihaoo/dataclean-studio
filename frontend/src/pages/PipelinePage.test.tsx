import { render, screen, waitFor } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PipelinePage from "./PipelinePage";
import { installFetch, errorResponse, jobDetail } from "../test/mocks";

const savedPipeline = {
  job_id: "abc12345",
  version: 1,
  steps: [
    {
      id: "dedupe-1",
      type: "dedupe",
      enabled: true,
      config: { mode: "exact", columns: [], keep: "first" },
    },
  ],
  created_at: "2026-09-30T10:00:00+00:00",
  updated_at: "2026-09-30T10:00:00+00:00",
};

const transformResult = {
  run_id: "run1",
  input_rows: 5,
  output_rows: 4,
  columns: ["name"],
  changed_cells: 2,
  steps: [
    {
      step_id: "dedupe-1",
      step_type: "dedupe",
      enabled: true,
      status: "applied",
      summary: "1 duplicate row(s) removed (first kept).",
      input_rows: 5,
      output_rows: 4,
      stats: { rows_removed: 1 },
      samples: [],
      removed_rows: [],
    },
  ],
  preview: [{ name: "John" }],
};

function renderPipeline(extra: Record<string, unknown> = {}) {
  const fetchMock = installFetch({
    // default pipeline handler: GET -> none saved, PUT -> echo saved, DELETE -> ok
    "/api/jobs/abc12345/pipeline": (_url: string, init?: RequestInit) => {
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "PUT") {
        const body = JSON.parse(String(init?.body));
        return {
          job_id: "abc12345",
          version: 1,
          steps: body.steps,
          created_at: "2026-09-30T10:00:00+00:00",
          updated_at: "2026-09-30T11:00:00+00:00",
        };
      }
      if (method === "DELETE") return { job_id: "abc12345", deleted: true };
      return errorResponse(404, "pipeline_not_found", "none saved");
    },
    "/api/jobs/abc12345/runs": [],
    "/api/jobs/abc12345": jobDetail,
    ...extra,
  });
  const rendered = render(
    <MemoryRouter initialEntries={["/jobs/abc12345/pipeline"]}>
      <Routes>
        <Route path="/jobs/:jobId/pipeline" element={<PipelinePage />} />
      </Routes>
    </MemoryRouter>
  );
  return { fetchMock, rendered };
}

async function addDedupeStep(user: UserEvent) {
  await user.click(screen.getByRole("button", { name: /remove duplicates/i }));
}

async function waitReady() {
  await screen.findByTestId("pipeline-empty");
}

describe("PipelinePage (editor)", () => {
  it("shows the empty state before any steps exist", async () => {
    renderPipeline();
    expect(await screen.findByText(/no steps yet/i)).toBeTruthy();
  });

  it("adds a dedupe step and shows its controls", async () => {
    renderPipeline();
    const user = userEvent.setup();
    await waitReady();
    await addDedupeStep(user);
    expect(screen.getByTestId("pipeline-steps").textContent).toContain("dedupe");
    expect(screen.getByLabelText("Mode")).toBeTruthy();
    expect(screen.getByLabelText("Keep")).toBeTruthy();
  });

  it("disables and re-enables a step", async () => {
    renderPipeline();
    const user = userEvent.setup();
    await waitReady();
    await addDedupeStep(user);
    await user.click(screen.getByRole("button", { name: "Disable" }));
    expect(screen.getByTestId("pipeline-steps").firstElementChild?.className).toContain("disabled");
    await user.click(screen.getByRole("button", { name: "Enable" }));
    expect(screen.getByTestId("pipeline-steps").firstElementChild?.className).not.toContain(
      "disabled"
    );
  });

  it("removes a step", async () => {
    renderPipeline();
    const user = userEvent.setup();
    await waitReady();
    await addDedupeStep(user);
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.getByText(/no steps yet/i)).toBeTruthy();
  });

  it("reorders steps via the up/down buttons", async () => {
    renderPipeline();
    const user = userEvent.setup();
    await waitReady();
    await user.click(screen.getByRole("button", { name: /normalize text/i }));
    await addDedupeStep(user);
    const ids = () =>
      Array.from(screen.getByTestId("pipeline-steps").querySelectorAll(".badge.warn")).map(
        (el) => el.textContent
      );
    expect(ids()).toEqual(["normalize", "dedupe"]);
    await user.click(screen.getByRole("button", { name: /move dedupe-\w+ up/i }));
    expect(ids()).toEqual(["dedupe", "normalize"]);
  });

  it("runs the pipeline (auto-saving first) and shows step results", async () => {
    const { fetchMock } = renderPipeline();
    // support GET (404), PUT (save), runs, transform and job detail
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.endsWith("/pipeline") && method === "PUT") {
        return new Response(
          JSON.stringify({ ...savedPipeline, steps: JSON.parse(String(init?.body)).steps }),
          { status: 200 }
        );
      }
      if (url.endsWith("/pipeline")) {
        return errorResponse(404, "pipeline_not_found", "none saved");
      }
      if (url.endsWith("/runs")) return new Response(JSON.stringify([]), { status: 200 });
      if (url.endsWith("/transform")) {
        return new Response(JSON.stringify(transformResult), { status: 200 });
      }
      return new Response(JSON.stringify(jobDetail), { status: 200 });
    });

    const user = userEvent.setup();
    await waitReady();
    await addDedupeStep(user);
    await user.click(screen.getByRole("button", { name: "Run pipeline" }));

    expect(await screen.findByTestId("run-results")).toBeTruthy();
    // the run auto-saved the editor configuration first
    const putCall = fetchMock.mock.calls.find(
      ([url, init]: [RequestInfo | URL, (RequestInit | undefined)?]) =>
        String(url).endsWith("/pipeline") && String(init?.method) === "PUT"
    );
    expect(putCall).toBeTruthy();
    const body = JSON.parse((putCall![1] as RequestInit).body as string);
    expect(body.steps[0].type).toBe("dedupe");
    // saved state feedback replaces the dirty hint
    expect(screen.getByTestId("save-state").textContent).toMatch(/saved configuration in use/i);
  });

  it("surfaces backend pipeline errors", async () => {
    renderPipeline({
      "/api/jobs/abc12345/transform": () =>
        errorResponse(400, "unknown_column", "Validation rule targets unknown column 'ghost'."),
    });
    const user = userEvent.setup();
    await waitReady();
    await addDedupeStep(user);
    await user.click(screen.getByRole("button", { name: "Run pipeline" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("unknown_column");
  });

  it("picks up pending renames from the schema page", async () => {
    sessionStorage.setItem(
      "dcstudio:pendingRename:abc12345",
      JSON.stringify({ cust_nm: "customer_name" })
    );
    renderPipeline();
    await waitFor(() => {
      expect(screen.getByTestId("pipeline-steps").textContent).toContain("rename");
      expect(screen.getByDisplayValue("customer_name")).toBeTruthy();
    });
  });
});

describe("PipelinePage (persistence)", () => {
  it("loads the saved pipeline into the editor on entry", async () => {
    renderPipeline({
      "/api/jobs/abc12345/pipeline": () => savedPipeline,
    });
    expect(await screen.findByTestId("pipeline-steps")).toBeTruthy();
    expect(screen.getByTestId("pipeline-steps").textContent).toContain("dedupe-1");
    expect(screen.getByTestId("save-state").textContent).toMatch(/saved configuration in use/i);
  });

  it("shows an error banner (not silence) when loading fails", async () => {
    renderPipeline({
      "/api/jobs/abc12345/pipeline": () =>
        errorResponse(500, "internal_error", "Unexpected server error."),
    });
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load the saved pipeline");
  });

  it("saves the pipeline and shows saved feedback", async () => {
    const { fetchMock } = renderPipeline();
    const user = userEvent.setup();
    await waitReady();
    await addDedupeStep(user);
    expect(screen.getByTestId("save-state").textContent).toMatch(/unsaved changes/i);

    await user.click(screen.getByRole("button", { name: /save pipeline/i }));
    await waitFor(() => {
      expect(screen.getByTestId("save-state").textContent).toMatch(/saved configuration/i);
    });
    const putCall = fetchMock.mock.calls.find(
      ([url, init]: [RequestInfo | URL, (RequestInit | undefined)?]) =>
        String(url).endsWith("/pipeline") && String(init?.method) === "PUT"
    );
    expect(putCall).toBeTruthy();
    const body = JSON.parse((putCall![1] as RequestInit).body as string);
    expect(body.steps).toHaveLength(1);
    expect(body.steps[0].type).toBe("dedupe");
  });

  it("shows an error and no success state when saving fails", async () => {
    renderPipeline({
      "/api/jobs/abc12345/pipeline": (_url: string, init?: RequestInit) =>
        (init?.method ?? "GET").toUpperCase() === "PUT"
          ? errorResponse(500, "internal_error", "Database is unavailable.")
          : errorResponse(404, "pipeline_not_found", "none saved"),
    });
    const user = userEvent.setup();
    await waitReady();
    await addDedupeStep(user);
    await user.click(screen.getByRole("button", { name: /save pipeline/i }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Database is unavailable.");
    // still dirty, no saved feedback
    expect(screen.getByTestId("save-state").textContent).toMatch(/unsaved changes/i);
  });

  it("restores the saved configuration after a reload", async () => {
    const { rendered: first } = renderPipeline();
    const user = userEvent.setup();
    await waitReady();
    await addDedupeStep(user);
    await user.click(screen.getByRole("button", { name: /save pipeline/i }));
    await waitFor(() => {
      expect(screen.getByTestId("save-state").textContent).toMatch(/saved configuration/i);
    });
    first.unmount();

    // fresh mount = what a browser refresh does
    renderPipeline({
      "/api/jobs/abc12345/pipeline": () => savedPipeline,
    });
    expect(await screen.findByTestId("pipeline-steps")).toBeTruthy();
    expect(screen.getByTestId("pipeline-steps").textContent).toContain("dedupe-1");
  });

  it("clearing the pipeline deletes the saved configuration", async () => {
    const { fetchMock } = renderPipeline({
      "/api/jobs/abc12345/pipeline": () => savedPipeline,
    });
    const user = userEvent.setup();
    await screen.findByTestId("pipeline-steps");
    await user.click(screen.getByRole("button", { name: /clear pipeline/i }));

    expect(await screen.findByTestId("pipeline-empty")).toBeTruthy();
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/pipeline") && String((init as RequestInit)?.method) === "DELETE"
      )
    ).toBe(true);
    expect(screen.getByTestId("save-state").textContent).toMatch(/not saved yet/i);
  });

  it("lists recent runs and restores a run's configuration on request", async () => {
    const { fetchMock } = renderPipeline({
      "/api/jobs/abc12345/runs": () => [
        {
          run_id: "run-aaaa",
          job_id: "abc12345",
          kind: "transform",
          status: "success",
          created_at: "2026-09-30T10:05:00+00:00",
          summary: {
            input_rows: 48,
            output_rows: 45,
            changed_cells: 79,
            pipeline: {
              version: 1,
              steps: [
                {
                  id: "norm-from-run",
                  type: "normalize",
                  enabled: true,
                  config: { columns: [{ column: "cust_nm", operations: ["trim"] }] },
                },
              ],
            },
          },
        },
        {
          run_id: "run-bbbb",
          job_id: "abc12345",
          kind: "validate",
          status: "success",
          created_at: "2026-09-30T10:01:00+00:00",
          summary: { rules: 2, errors_total: 6 },
        },
      ],
    });
    const user = userEvent.setup();
    await waitReady();
    expect(await screen.findByTestId("run-history")).toBeTruthy();
    expect(screen.getAllByTestId("run-row")).toHaveLength(2);
    expect(screen.getByText(/48 → 45 rows/)).toBeTruthy();
    expect(screen.getByText(/6 error\(s\)/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /restore config/i }));
    await waitFor(() => {
      expect(screen.getByTestId("pipeline-steps").textContent).toContain("norm-from-run");
    });
    // restored config becomes dirty until saved
    expect(screen.getByTestId("save-state").textContent).toMatch(/unsaved changes/i);
    // PUT payload uses the restored steps
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/pipeline") &&
          String((init as RequestInit)?.method) === "PUT" &&
          String(init?.body).includes("norm-from-run")
      )
    ).toBe(false); // not saved automatically by restoring alone
  });
});
