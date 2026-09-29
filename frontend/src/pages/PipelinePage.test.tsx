import { render, screen, waitFor } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PipelinePage from "./PipelinePage";
import { installFetch, errorResponse, jobDetail } from "../test/mocks";

function renderPipeline() {
  return render(
    <MemoryRouter initialEntries={["/jobs/abc12345/pipeline"]}>
      <Routes>
        <Route path="/jobs/:jobId/pipeline" element={<PipelinePage />} />
      </Routes>
    </MemoryRouter>
  );
}

async function addDedupeStep(user: UserEvent) {
  await user.click(screen.getByRole("button", { name: /remove duplicates/i }));
}

describe("PipelinePage", () => {
  it("shows the empty state before any steps exist", async () => {
    installFetch({ "/api/jobs/abc12345": jobDetail });
    renderPipeline();
    expect(await screen.findByText(/no steps yet/i)).toBeTruthy();
  });

  it("adds a dedupe step and shows its controls", async () => {
    installFetch({ "/api/jobs/abc12345": jobDetail });
    renderPipeline();
    const user = userEvent.setup();
    await addDedupeStep(user);
    expect(screen.getByTestId("pipeline-steps").textContent).toContain("dedupe");
    expect(screen.getByLabelText("Mode")).toBeTruthy();
    expect(screen.getByLabelText("Keep")).toBeTruthy();
  });

  it("disables and re-enables a step", async () => {
    installFetch({ "/api/jobs/abc12345": jobDetail });
    renderPipeline();
    const user = userEvent.setup();
    await addDedupeStep(user);
    await user.click(screen.getByRole("button", { name: "Disable" }));
    expect(screen.getByTestId("pipeline-steps").firstElementChild?.className).toContain("disabled");
    await user.click(screen.getByRole("button", { name: "Enable" }));
    expect(screen.getByTestId("pipeline-steps").firstElementChild?.className).not.toContain(
      "disabled"
    );
  });

  it("removes a step", async () => {
    installFetch({ "/api/jobs/abc12345": jobDetail });
    renderPipeline();
    const user = userEvent.setup();
    await addDedupeStep(user);
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.getByText(/no steps yet/i)).toBeTruthy();
  });

  it("clears the whole pipeline", async () => {
    installFetch({ "/api/jobs/abc12345": jobDetail });
    renderPipeline();
    const user = userEvent.setup();
    await addDedupeStep(user);
    await user.click(screen.getByRole("button", { name: /clear pipeline/i }));
    expect(screen.getByText(/no steps yet/i)).toBeTruthy();
  });

  it("reorders steps via the up/down buttons", async () => {
    installFetch({ "/api/jobs/abc12345": jobDetail });
    renderPipeline();
    const user = userEvent.setup();
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

  it("runs the pipeline and shows per-step before/after samples", async () => {
    installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/transform": () => ({
        run_id: "run1",
        input_rows: 5,
        output_rows: 4,
        columns: ["name"],
        changed_cells: 2,
        steps: [
          {
            step_id: "normalize-1",
            step_type: "normalize",
            enabled: true,
            status: "applied",
            summary: "2 cell(s) normalized.",
            input_rows: 5,
            output_rows: 5,
            stats: {},
            samples: [{ row: 1, column: "cust_nm", before: "  John  ", after: "John" }],
            removed_rows: [],
          },
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
            removed_rows: [{ cust_nm: "John", mail: "j@x.com" }],
          },
        ],
        preview: [{ name: "John" }],
      }),
    });
    renderPipeline();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /normalize text/i }));
    await user.click(screen.getByRole("button", { name: "Run pipeline" }));
    expect(await screen.findByTestId("run-results")).toBeTruthy();
    const before = document.querySelector(".ba-before");
    expect(before?.textContent).toBe("  John  ");
    const after = document.querySelector(".ba-after");
    expect(after?.textContent).toBe("John");
    expect(screen.getByText(/1 duplicate row\(s\) removed/i)).toBeTruthy();
    expect(screen.getByText(/5 → 4 rows/)).toBeTruthy();
  });

  it("surfaces backend pipeline errors", async () => {
    installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/transform": () =>
        errorResponse(400, "unknown_column", "Validation rule targets unknown column 'ghost'."),
    });
    renderPipeline();
    const user = userEvent.setup();
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
    installFetch({ "/api/jobs/abc12345": jobDetail });
    renderPipeline();
    await waitFor(() => {
      expect(screen.getByTestId("pipeline-steps").textContent).toContain("rename");
      expect(screen.getByDisplayValue("customer_name")).toBeTruthy();
    });
  });
});
