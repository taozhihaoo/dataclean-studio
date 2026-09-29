import { render, screen, waitFor } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ValidationPage from "./ValidationPage";
import { installFetch, errorResponse, jobDetail, validationOk } from "../test/mocks";

function renderValidation() {
  return render(
    <MemoryRouter initialEntries={["/jobs/abc12345/validation"]}>
      <Routes>
        <Route path="/jobs/:jobId/validation" element={<ValidationPage />} />
      </Routes>
    </MemoryRouter>
  );
}

/** The rule-picker options load with the job detail; wait for the target. */
async function addRule(user: UserEvent, optionLabel: RegExp | string) {
  await screen.findByLabelText("Add rule for column");
  await screen.findByRole("option", { name: optionLabel });
  await user.selectOptions(
    screen.getByLabelText("Add rule for column"),
    screen.getByRole("option", { name: optionLabel })
  );
}

describe("ValidationPage", () => {
  it("adds an email rule for the mail column and runs validation", async () => {
    const fetchMock = installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/validate": () => validationOk,
    });
    renderValidation();
    const user = userEvent.setup();

    await addRule(user, /mail — valid email/i);
    expect(screen.getAllByTestId("rule-row").length).toBe(1);
    expect(screen.getByLabelText("Rule column")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /run validation/i }));
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/validate"));
      expect(call).toBeTruthy();
      const body = JSON.parse((call![1] as RequestInit).body as string);
      expect(body.rules).toEqual([{ column: "mail", rule: "email" }]);
    });
    expect(await screen.findByText(/all rules passed/i)).toBeTruthy();
  });

  it("configures a numeric range with min and max", async () => {
    const fetchMock = installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/validate": () => validationOk,
    });
    renderValidation();
    const user = userEvent.setup();
    await addRule(user, /age — numeric range/i);
    await user.clear(screen.getByLabelText("Min"));
    await user.type(screen.getByLabelText("Min"), "0");
    await user.clear(screen.getByLabelText("Max"));
    await user.type(screen.getByLabelText("Max"), "120");
    await user.click(screen.getByRole("button", { name: /run validation/i }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/validate"));
      const body = JSON.parse((call![1] as RequestInit).body as string);
      expect(body.rules[0]).toMatchObject({ column: "age", rule: "numeric_range", min: 0, max: 120 });
    });
  });

  it("collects allowed values from a comma separated list", async () => {
    const fetchMock = installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/validate": () => validationOk,
    });
    renderValidation();
    const user = userEvent.setup();
    await addRule(user, /cust_nm — allowed values/i);
    await user.type(screen.getByLabelText(/allowed values/i), "active, inactive");
    await user.click(screen.getByRole("button", { name: /run validation/i }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/validate"));
      const body = JSON.parse((call![1] as RequestInit).body as string);
      expect(body.rules[0]).toMatchObject({
        column: "cust_nm",
        rule: "allowed_values",
        values: ["active", "inactive"],
      });
    });
  });

  it("removes a rule", async () => {
    installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/validate": () => validationOk,
    });
    renderValidation();
    const user = userEvent.setup();
    await addRule(user, /mail — valid email/i);
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.queryByTestId("rule-row")).toBeNull();
  });

  it("shows errors from invalid rules", async () => {
    installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/validate": () =>
        errorResponse(422, "validation_error", "Invalid request: regex rule requires 'pattern'"),
    });
    renderValidation();
    const user = userEvent.setup();
    await addRule(user, /cust_nm — matches regex/i);
    await user.click(screen.getByRole("button", { name: /run validation/i }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("validation_error");
  });

  it("renders failed results with samples", async () => {
    installFetch({
      "/api/jobs/abc12345": jobDetail,
      "/api/jobs/abc12345/validate": () => ({
        ...validationOk,
        passed: false,
        error_count_total: 1,
        rules: [
          {
            column: "mail",
            rule: "email",
            total_values: 2,
            error_count: 1,
            error_rate: 0.5,
            passed: false,
            samples: [{ row: 2, value: "broken", reason: "not a valid email address" }],
          },
        ],
      }),
    });
    renderValidation();
    const user = userEvent.setup();
    await addRule(user, /mail — valid email/i);
    await user.click(screen.getByRole("button", { name: /run validation/i }));
    expect(await screen.findByText(/1 error\(s\) found/i)).toBeTruthy();
    expect(screen.getByText("broken")).toBeTruthy();
    expect(screen.getByText("not a valid email address")).toBeTruthy();
  });
});
