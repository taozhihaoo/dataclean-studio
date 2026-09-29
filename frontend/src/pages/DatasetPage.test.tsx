import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import DatasetPage from "./DatasetPage";
import { installFetch, installFetchError, jobDetail, meta, preview } from "../test/mocks";

function renderDataset() {
  return render(
    <MemoryRouter initialEntries={["/jobs/abc12345"]}>
      <Routes>
        <Route path="/jobs/:jobId" element={<DatasetPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("DatasetPage", () => {
  it("renders the data preview with row counts", async () => {
    installFetch({
      "/api/jobs/abc12345/preview": preview,
      "/api/jobs/abc12345": jobDetail,
      "/api/meta": meta,
    });
    renderDataset();
    expect(await screen.findByTestId("data-table")).toBeTruthy();
    expect(screen.getByText(/2 rows · 3 columns/i)).toBeTruthy();
    expect(screen.getByText("John")).toBeTruthy();
  });

  it("switches to the schema tab and shows detected types", async () => {
    installFetch({
      "/api/jobs/abc12345/preview": preview,
      "/api/jobs/abc12345": jobDetail,
      "/api/meta": meta,
    });
    renderDataset();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: /schema/i }));
    expect(await screen.findByTestId("schema-table")).toBeTruthy();
    expect(screen.getAllByText("email").length).toBeGreaterThan(0);
    expect(screen.getAllByText("integer").length).toBeGreaterThan(0);
  });

  it("requests heuristic suggestions and lists them", async () => {
    const fetchMock = installFetch({
      "/api/jobs/abc12345/preview": preview,
      "/api/jobs/abc12345": jobDetail,
      "/api/meta": meta,
      "/api/jobs/abc12345/infer-mapping": () => ({
        provider: "heuristic",
        targets_used: ["customer_name"],
        suggestions: [
          { source: "cust_nm", target: "customer_name", confidence: 0.95, rationale: "synonym", provider: "heuristic" },
        ],
      }),
    });
    renderDataset();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: /schema/i }));
    await user.click(await screen.findByRole("button", { name: /suggest mapping/i }));
    expect(await screen.findByTestId("inference-results")).toBeTruthy();
    expect(screen.getAllByText("cust_nm").length).toBeGreaterThan(0);
    expect(screen.getByText("customer_name")).toBeTruthy();
    expect(
      fetchMock.mock.calls.some(([url, init]) =>
        String(url).includes("infer-mapping") && String((init as RequestInit)?.body).includes("heuristic")
      )
    ).toBe(true);
  });

  it("shows an error banner when preview loading fails", async () => {
    installFetchError(410, {
      error: { code: "dataset_missing", message: "The stored dataset for this job is missing." },
    });
    renderDataset();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("missing");
  });

  it("stores pending renames and navigates to the pipeline", async () => {
    installFetch({
      "/api/jobs/abc12345/preview": preview,
      "/api/jobs/abc12345": jobDetail,
      "/api/meta": meta,
      "/api/jobs/abc12345/infer-mapping": () => ({
        provider: "heuristic",
        targets_used: [],
        suggestions: [
          { source: "mail", target: "email", confidence: 0.9, rationale: "synonym", provider: "heuristic" },
        ],
      }),
    });
    renderDataset();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: /schema/i }));
    await user.click(await screen.findByRole("button", { name: /suggest mapping/i }));
    await screen.findByTestId("inference-results");
    await user.click(screen.getByRole("button", { name: /apply as rename step/i }));
    await waitFor(() => {
      expect(sessionStorage.getItem("dcstudio:pendingRename:abc12345") ?? "").toContain("email");
    });
  });
});
