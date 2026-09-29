import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import UploadPage from "./UploadPage";
import { installFetch, errorResponse, jobDetail } from "../test/mocks";

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

function renderUpload() {
  return render(
    <MemoryRouter initialEntries={["/upload"]}>
      <Routes>
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/jobs/:jobId" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("UploadPage", () => {
  it("uploads a file and navigates to the dataset page", async () => {
    const fetchMock = installFetch({
      "/api/files/upload": () => jobDetail,
      "/api/meta": { version: "1.0.0", max_upload_mb: 25, preview_row_limit: 50 },
    });
    renderUpload();
    const user = userEvent.setup();
    const file = new File(["a,b\n1,2"], "people.csv", { type: "text/csv" });
    await user.upload(screen.getByTestId("file-input"), file);

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/files/upload"))).toBe(
        true
      );
    });
    expect(await screen.findByText(/uploaded:/i)).toBeTruthy();
    expect(await screen.findByTestId("location").then((el) => el.textContent)).toBe(
      `/jobs/${jobDetail.job_id}`
    );
  });

  it("shows a friendly server-side error for a broken CSV", async () => {
    // The picker's accept attribute filters extensions client-side; the
    // server still rejects files whose *content* is not a parseable table.
    installFetch({
      "/api/files/upload": () =>
        errorResponse(
          400,
          "invalid_encoding",
          "The file contains binary data and cannot be read as a CSV."
        ),
      "/api/meta": { version: "1.0.0", max_upload_mb: 25, preview_row_limit: 50 },
    });
    renderUpload();
    const user = userEvent.setup();
    await user.upload(
      screen.getByTestId("file-input"),
      new File([Uint8Array.of(0, 1, 2, 3)], "broken.csv", { type: "text/csv" })
    );
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("invalid_encoding");
    expect(alert.textContent).toContain("binary data");
  });

  it("shows the demo data hint", async () => {
    installFetch({
      "/api/meta": { version: "1.0.0", max_upload_mb: 25, preview_row_limit: 50 },
    });
    renderUpload();
    expect(await screen.findByText(/demo-data\/sample_customers\.csv/i)).toBeTruthy();
  });
});
