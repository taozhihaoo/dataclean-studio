import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ReportPage from "./ReportPage";
import { installFetch, installFetchError, jobDetail } from "../test/mocks";

const report = {
  job_id: "abc12345",
  filename: "sample_customers.csv",
  generated_at: "2026-09-30T10:05:00+00:00",
  total_rows: 48,
  total_columns: 8,
  null_counts: { cust_nm: 0, mail: 2, ph_no: 1 },
  null_cells_total: 3,
  duplicate_rows: 4,
  invalid_email_count: 5,
  invalid_date_count: 2,
  original_rows: 48,
  rows_delta: 0,
  validation: null,
  transform: null,
  merge: null,
  columns: jobDetail.columns,
};

function renderReport() {
  return render(
    <MemoryRouter initialEntries={["/jobs/abc12345/report"]}>
      <Routes>
        <Route path="/jobs/:jobId/report" element={<ReportPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ReportPage", () => {
  it("renders summary statistics", async () => {
    installFetch({
      "/api/jobs/abc12345/quality-report": () => report,
    });
    renderReport();
    expect(await screen.findByText("Total rows")).toBeTruthy();
    expect(screen.getByText("Duplicate rows")).toBeTruthy();
    expect(screen.getByText("Invalid emails")).toBeTruthy();
    expect(screen.getAllByText("48").length).toBeGreaterThan(0);
  });

  it("renders per-column statistics with invalid markers", async () => {
    installFetch({
      "/api/jobs/abc12345/quality-report": () => report,
    });
    renderReport();
    expect(await screen.findByTestId("report-columns")).toBeTruthy();
    expect(screen.getByText("cust_nm")).toBeTruthy();
    expect(screen.getByText("email")).toBeTruthy();
  });

  it("flags negative findings in red tones", async () => {
    installFetch({
      "/api/jobs/abc12345/quality-report": () => report,
    });
    renderReport();
    const invalidCard = await screen.findByText("Invalid emails");
    expect(invalidCard.closest(".stat-card")?.className).toContain("negative");
  });

  it("shows an error when the report cannot be generated", async () => {
    installFetchError(404, {
      error: { code: "job_not_found", message: "Job was not found." },
    });
    renderReport();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Job was not found");
  });
});
