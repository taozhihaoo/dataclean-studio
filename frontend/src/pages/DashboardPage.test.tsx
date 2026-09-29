import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import DashboardPage from "./DashboardPage";
import { installFetch, installFetchError, jobDetail, meta } from "../test/mocks";

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>
  );
}

describe("DashboardPage", () => {
  it("shows an empty state when there are no jobs", async () => {
    installFetch({
      "/api/jobs": [],
      "/api/meta": meta,
    });
    renderDashboard();
    expect(await screen.findByText(/no datasets yet/i)).toBeTruthy();
    expect(screen.getByText(/sample_customers\.csv/i)).toBeTruthy();
  });

  it("lists uploaded jobs with status and rows", async () => {
    installFetch({
      "/api/jobs": [jobDetail],
      "/api/meta": meta,
    });
    renderDashboard();
    expect(await screen.findByText("sample_customers.csv")).toBeTruthy();
    expect(screen.getByTestId("jobs-table").textContent).toContain("ready");
  });

  it("deletes a job and refreshes the list", async () => {
    const fetchMock = installFetch({
      "/api/jobs": () => [jobDetail],
      "/api/meta": meta,
    });
    renderDashboard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/jobs/abc12345"),
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("shows an error banner when the API fails", async () => {
    installFetchError(500, {
      error: { code: "internal_error", message: "Unexpected server error." },
    });
    renderDashboard();
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/unexpected server error/i)).toBeTruthy();
  });
});
