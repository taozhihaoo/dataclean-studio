import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ExportPage from "./ExportPage";
import { installFetch, errorResponse, jobDetail } from "../test/mocks";

function renderExport() {
  return render(
    <MemoryRouter initialEntries={["/jobs/abc12345/export"]}>
      <Routes>
        <Route path="/jobs/:jobId/export" element={<ExportPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ExportPage", () => {
  it("shows transform stats from the last run", async () => {
    installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/runs": [
        {
          run_id: "r1",
          job_id: "abc12345",
          kind: "transform",
          status: "success",
          created_at: "2026-09-30T10:00:00+00:00",
          summary: { input_rows: 5, output_rows: 4, changed_cells: 7 },
        },
      ],
    });
    renderExport();
    expect(await screen.findByText("Input rows")).toBeTruthy();
    expect(screen.getByText("Changed cells")).toBeTruthy();
  });

  it("hints at the pipeline when no transform ran yet", async () => {
    installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/runs": [],
    });
    renderExport();
    expect(await screen.findByText(/not been transformed yet/i)).toBeTruthy();
  });

  it("downloads a CSV export with the requested filename", async () => {
    const downloadSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {});
    URL.createObjectURL = vi.fn(() => "blob:fake");
    URL.revokeObjectURL = vi.fn();
    const fetchMock = installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/runs": [],
    });
    // downloadFile hits the same fetch; add a handler with headers
    const response = new Response("a,b\n", {
      status: 200,
      headers: { "Content-Disposition": 'attachment; filename="cleaned_data.csv"' },
    });
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.endsWith("/export")) return response;
      const body = url.includes("/runs") ? [] : jobDetail;
      return new Response(JSON.stringify(body), { status: 200 });
    });

    renderExport();
    const user = userEvent.setup();
    // wait for the derived default before editing
    await screen.findByDisplayValue("sample_customers_clean");
    const filenameInput = screen.getByLabelText(/filename/i);
    await user.clear(filenameInput);
    await user.type(filenameInput, "my_clean_data");
    await user.click(screen.getByRole("button", { name: /export csv/i }));

    await waitFor(() => {
      const exportCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/export"));
      expect(exportCall).toBeTruthy();
      const body = JSON.parse((exportCall![1] as RequestInit).body as string);
      expect(body).toEqual({ file_format: "csv", filename: "my_clean_data", guard_formulas: true });
    });
    expect(await screen.findByText(/download started/i)).toBeTruthy();
    downloadSpy.mockRestore();
  });

  it("switches format and disables formula guard", async () => {
    const downloadSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {});
    URL.createObjectURL = vi.fn(() => "blob:fake");
    URL.revokeObjectURL = vi.fn();
    const fetchMock = installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/runs": [],
    });
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.endsWith("/export")) {
        return new Response("{}", {
          status: 200,
          headers: { "Content-Disposition": 'attachment; filename="x.json"' },
        });
      }
      const body = url.includes("/runs") ? [] : jobDetail;
      return new Response(JSON.stringify(body), { status: 200 });
    });

    renderExport();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "JSON" }));
    await user.click(screen.getByLabelText(/guard against formula injection/i));
    await user.click(screen.getByRole("button", { name: /export json/i }));

    await waitFor(() => {
      const exportCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/export"));
      const body = JSON.parse((exportCall![1] as RequestInit).body as string);
      expect(body.file_format).toBe("json");
      expect(body.guard_formulas).toBe(false);
    });
    downloadSpy.mockRestore();
  });

  it("surfaces export errors", async () => {
    installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/runs": [],
      "/api/jobs/abc12345/export": () =>
        errorResponse(400, "unsupported_export_format", "Unsupported export format 'parquet'."),
    });
    renderExport();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /export csv/i }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("unsupported_export_format");
  });
});
