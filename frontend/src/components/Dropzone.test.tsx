import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dropzone } from "./Dropzone";

describe("Dropzone", () => {
  it("opens the file picker on click and emits the selected file", async () => {
    const onFile = vi.fn();
    render(<Dropzone onFile={onFile} />);
    const user = userEvent.setup();

    const input = screen.getByTestId("file-input");
    const clickSpy = vi.spyOn(input, "click");
    await user.click(screen.getByRole("button", { name: /upload a csv/i }));
    expect(clickSpy).toHaveBeenCalled();

    const file = new File(["a,b\n1,2"], "data.csv", { type: "text/csv" });
    await user.upload(input, file);
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("accepts dropped files", () => {
    const onFile = vi.fn();
    render(<Dropzone onFile={onFile} />);
    const zone = screen.getByTestId("dropzone");
    const file = new File(["x"], "dropped.xlsx", { type: "application/octet-stream" });
    fireEvent.drop(zone, { dataTransfer: fakeDataTransfer(file) });
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("marks itself as dragging on dragover", () => {
    render(<Dropzone onFile={vi.fn()} />);
    const zone = screen.getByTestId("dropzone");
    fireEvent.dragOver(zone);
    expect(zone.className).toContain("dragover");
  });

  it("ignores interactions while disabled", async () => {
    const onFile = vi.fn();
    render(<Dropzone onFile={onFile} disabled />);
    const input = screen.getByTestId("file-input");
    const clickSpy = vi.spyOn(input, "click");
    await userEvent.click(screen.getByRole("button", { name: /upload a csv/i }));
    expect(clickSpy).not.toHaveBeenCalled();
  });
});

/** jsdom lacks DataTransfer; a structural fake is enough for the handler. */
function fakeDataTransfer(file: File): DataTransfer {
  return { items: { add: () => undefined }, files: [file] } as unknown as DataTransfer;
}
