import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import JobLayout from "./JobLayout";

describe("JobLayout stepper", () => {
  it("builds step links with a slash between the job id and the step", () => {
    render(
      <MemoryRouter initialEntries={["/jobs/abc12345"]}>
        <Routes>
          <Route
            path="/jobs/:jobId/*"
            element={
              <JobLayout jobId="abc12345">
                <div />
              </JobLayout>
            }
          />
        </Routes>
      </MemoryRouter>
    );
    const pipeline = screen.getByRole("link", { name: /2 Clean & Transform/ });
    expect(pipeline.getAttribute("href")).toBe("/jobs/abc12345/pipeline");
    const dataset = screen.getByRole("link", { name: /1 Dataset/ });
    expect(dataset.getAttribute("href")).toBe("/jobs/abc12345");
    const report = screen.getByRole("link", { name: /5 Quality Report/ });
    expect(report.getAttribute("href")).toBe("/jobs/abc12345/report");
  });
});
