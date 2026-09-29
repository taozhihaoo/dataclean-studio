import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataTable } from "./DataTable";

const rows = [
  { name: "Jo", age: "34", note: null },
  { name: "Al", age: "", note: "vip" },
];

describe("DataTable", () => {
  it("renders headers and cells", () => {
    render(<DataTable columns={["name", "age", "note"]} rows={rows} />);
    expect(screen.getByRole("columnheader", { name: "name" })).toBeTruthy();
    expect(screen.getByText("Jo")).toBeTruthy();
    expect(screen.getByText("vip")).toBeTruthy();
  });

  it("marks null cells distinctly from empty strings", () => {
    render(<DataTable columns={["name", "age", "note"]} rows={rows} />);
    expect(screen.getByText("∅ null")).toBeTruthy();
    expect(screen.getByText('""')).toBeTruthy();
  });

  it("limits rendered rows when maxRows is set", () => {
    const many = Array.from({ length: 30 }, (_, i) => ({ name: `row${i}` }));
    render(<DataTable columns={["name"]} rows={many} maxRows={10} />);
    expect(screen.getByText("row9")).toBeTruthy();
    expect(screen.queryByText("row10")).toBeNull();
  });

  it("highlights changed columns", () => {
    render(<DataTable columns={["name", "age"]} rows={rows} changedColumns={["age"]} />);
    const header = screen.getByRole("columnheader", { name: "age" });
    expect(header.className).toContain("changed");
  });
});
