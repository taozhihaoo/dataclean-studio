import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import MergePage from "./MergePage";
import { installFetch, errorResponse } from "../test/mocks";

const jobs = [
  { job_id: "job-aaaaaaaa", filename: "customers_2024.csv", source: "upload", status: "ready", row_count: 10, column_count: 3, created_at: "", updated_at: "" },
  { job_id: "job-bbbbbbbb", filename: "customers_2025.csv", source: "upload", status: "ready", row_count: 12, column_count: 4, created_at: "", updated_at: "" },
];

function renderMerge() {
  return render(
    <MemoryRouter initialEntries={["/merge"]}>
      <MergePage />
    </MemoryRouter>
  );
}

describe("MergePage", () => {
  it("asks for two datasets when fewer are available", async () => {
    installFetch({ "/api/jobs": jobs.slice(0, 1) });
    renderMerge();
    expect(await screen.findByText(/need at least two datasets/i)).toBeTruthy();
  });

  it("selects datasets and merges them in union mode", async () => {
    const fetchMock = installFetch({
      "/api/jobs": () => jobs,
      "/api/merge": () => ({
        job_id: "merged-01",
        filename: "merged_2_files.csv",
        mode: "union",
        input_files: [],
        output_rows: 22,
        output_columns: 4,
        columns: [],
        null_cells_filled: 10,
      }),
    });
    renderMerge();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("checkbox", { name: /customers_2024/i }));
    await user.click(screen.getByRole("checkbox", { name: /customers_2025/i }));
    await user.click(screen.getByRole("button", { name: /merge 2 datasets/i }));

    expect(await screen.findByText(/merged into/i)).toBeTruthy();
    const mergeCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/merge"));
    const body = JSON.parse((mergeCall![1] as RequestInit).body as string);
    expect(body.mode).toBe("union");
    expect(body.files.map((f: { job_id: string }) => f.job_id).sort()).toEqual([
      "job-aaaaaaaa",
      "job-bbbbbbbb",
    ]);
  });

  it("disables merging until two datasets are selected", async () => {
    installFetch({ "/api/jobs": () => jobs });
    renderMerge();
    const user = userEvent.setup();
    await screen.findByTestId("merge-table");
    const button = screen.getByRole("button", { name: /merge/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    await user.click(screen.getByRole("checkbox", { name: /customers_2024/i }));
    expect(button.disabled).toBe(true);
    await user.click(screen.getByRole("checkbox", { name: /customers_2025/i }));
    expect(button.disabled).toBe(false);
  });

  it("surfaces merge errors (duplicate input)", async () => {
    installFetch({
      "/api/jobs": () => jobs,
      "/api/merge": () =>
        errorResponse(400, "duplicate_merge_input", "Job 'job-aaaaaaaa' is listed more than once."),
    });
    renderMerge();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("checkbox", { name: /customers_2024/i }));
    await user.click(screen.getByRole("checkbox", { name: /customers_2025/i }));
    await user.click(screen.getByRole("button", { name: /merge 2 datasets/i }));
    expect((await screen.findByRole("alert")).textContent).toContain("duplicate_merge_input");
  });
});
