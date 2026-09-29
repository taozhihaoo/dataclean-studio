import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import UploadPage from "./UploadPage";
import { installFetch, jobDetail } from "../test/mocks";

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

function csvFile(name: string, content = "a,b\n1,2\n"): File {
  return new File([content], name, { type: "text/csv" });
}

async function uploadFiles(user: ReturnType<typeof userEvent.setup>, files: File[]) {
  await user.upload(screen.getByTestId("file-input"), files);
}

const meta = { version: "1.0.0", max_upload_mb: 25, preview_row_limit: 50 };

function uploaded(filename: string, jobId: string, row_count = 2): object {
  return {
    filename,
    stored_filename: filename,
    status: "uploaded",
    job_id: jobId,
    row_count,
    column_count: 2,
    size_bytes: 10,
    error: null,
  };
}

function failed(filename: string, code: string, message: string): object {
  return {
    filename,
    stored_filename: null,
    status: "failed",
    job_id: null,
    row_count: null,
    column_count: null,
    size_bytes: null,
    error: { code, message },
  };
}

describe("UploadPage (batch upload)", () => {
  it("uploads several files and shows an independent success row per file", async () => {
    const fetchMock = installFetch({
      "/api/meta": meta,
      "/api/files/upload-batch": () => ({
        results: [uploaded("one.csv", "job-one-aaaa"), uploaded("two.csv", "job-two-bbbb", 3)],
        uploaded: 2,
        failed: 0,
      }),
    });
    renderUpload();
    const user = userEvent.setup();
    await uploadFiles(user, [csvFile("one.csv"), csvFile("two.csv")]);

    const rows = await screen.findAllByTestId("upload-item");
    expect(rows).toHaveLength(2);
    expect(rows[0].getAttribute("data-status")).toBe("success");
    expect(rows[1].getAttribute("data-status")).toBe("success");
    expect(screen.getByText("2 × 2")).toBeTruthy();
    expect(screen.getByText("3 × 2")).toBeTruthy();
    const links = Array.from(document.querySelectorAll("a")).filter((a) =>
      a.textContent?.includes("open dataset")
    );
    expect(links.map((a) => a.getAttribute("href"))).toContain("/jobs/job-one-aaaa");
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).endsWith("/api/files/upload-batch"))
    ).toBe(true);
  });

  it("marks a failing file as failed without blocking the others", async () => {
    installFetch({
      "/api/meta": meta,
      "/api/files/upload-batch": () => ({
        results: [
          uploaded("good.csv", "job-good-0001", 1),
          failed(
            "broken.csv",
            "invalid_encoding",
            "The file contains binary data and cannot be read as a CSV."
          ),
        ],
        uploaded: 1,
        failed: 1,
      }),
    });
    renderUpload();
    const user = userEvent.setup();
    await uploadFiles(user, [csvFile("good.csv"), csvFile("broken.csv")]);

    const rows = await screen.findAllByTestId("upload-item");
    expect(rows[0].getAttribute("data-status")).toBe("success");
    expect(rows[1].getAttribute("data-status")).toBe("failed");
    expect(screen.getByText(/invalid_encoding/)).toBeTruthy();
    expect(screen.getByText(/binary data/)).toBeTruthy();
    // the successful file is still usable
    expect(screen.getByRole("link", { name: /open dataset/i })).toBeTruthy();
  });

  it("retries only the failed file and flips it to success", async () => {
    const failFirst = true;
    installFetch({
      "/api/meta": meta,
      "/api/files/upload-batch": () => ({
        results: [
          failFirst
            ? failed("flaky.csv", "server_error", "boom")
            : uploaded("flaky.csv", "job-retry-009", 5),
        ],
        uploaded: failFirst ? 0 : 1,
        failed: failFirst ? 1 : 0,
      }),
      "/api/files/upload": () => jobDetail,
    });
    renderUpload();
    const user = userEvent.setup();
    await uploadFiles(user, [csvFile("flaky.csv")]);
    expect((await screen.findAllByTestId("upload-item"))[0].getAttribute("data-status")).toBe(
      "failed"
    );

    await user.click(screen.getByRole("button", { name: "Retry" }));
    const rows = await screen.findAllByTestId("upload-item");
    expect(rows[0].getAttribute("data-status")).toBe("success");
  });

  it("single file upload still navigates straight to the dataset", async () => {
    installFetch({
      "/api/meta": meta,
      "/api/files/upload-batch": () => ({
        results: [uploaded("solo.csv", jobDetail.job_id)],
        uploaded: 1,
        failed: 0,
      }),
    });
    renderUpload();
    const user = userEvent.setup();
    await uploadFiles(user, [csvFile("solo.csv")]);
    await waitFor(
      () => {
        expect(screen.getByTestId("location").textContent).toBe(`/jobs/${jobDetail.job_id}`);
      },
      { timeout: 2000 }
    );
  });

  it("caps the batch at 10 files and reports the skipped ones", async () => {
    const fetchMock = installFetch({
      "/api/meta": meta,
      "/api/files/upload-batch": () => ({
        results: Array.from({ length: 10 }, (_, i) => uploaded(`f${i}.csv`, `job-${i}-aaaaaaa`, 1)),
        uploaded: 10,
        failed: 0,
      }),
    });
    renderUpload();
    const user = userEvent.setup();
    await uploadFiles(
      user,
      Array.from({ length: 12 }, (_, i) => csvFile(`f${i}.csv`))
    );
    expect(await screen.findAllByTestId("upload-item")).toHaveLength(10);
    expect(screen.getByText(/only the first 10 files/i)).toBeTruthy();
    const batchCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url).endsWith("/api/files/upload-batch")
    );
    const sent = (batchCalls[0][1] as RequestInit).body as FormData;
    expect(sent.getAll("files")).toHaveLength(10);
  });

  it("shows an error banner when the whole batch request fails, rows stay listed", async () => {
    installFetchErrorWrapper();
    renderUpload();
    const user = userEvent.setup();
    await uploadFiles(user, [csvFile("a.csv"), csvFile("b.csv")]);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/timed out/i);
    const rows = await screen.findAllByTestId("upload-item");
    expect(rows.map((r) => r.getAttribute("data-status"))).toEqual(["failed", "failed"]);
  });

  function installFetchErrorWrapper() {
    installFetch({
      "/api/meta": meta,
      "/api/files/upload-batch": () => {
        throw Object.assign(new Error("The request timed out. Please try again."), {
          code: "timeout",
        });
      },
    });
  }
});
