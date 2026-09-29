import { describe, expect, it } from "vitest";
import { formatBytes, formatDateTime, formatNumber, truncate } from "./format";

describe("formatBytes", () => {
  it("formats bytes and kilobytes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
  });

  it("formats megabytes", () => {
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("renders null as an em dash", () => {
    expect(formatBytes(null)).toBe("—");
  });
});

describe("formatNumber", () => {
  it("adds thousands separators", () => {
    expect(formatNumber(12345)).toBe("12,345");
  });

  it("renders null as an em dash", () => {
    expect(formatNumber(null)).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("returns an em dash for missing values", () => {
    expect(formatDateTime(null)).toBe("—");
  });

  it("returns the input for unparseable values", () => {
    expect(formatDateTime("not-a-date")).toBe("not-a-date");
  });

  it("formats ISO timestamps", () => {
    const out = formatDateTime("2026-09-30T10:00:00Z");
    expect(out).toMatch(/2026/);
  });
});

describe("truncate", () => {
  it("keeps short strings", () => {
    expect(truncate("abc", 10)).toBe("abc");
  });

  it("truncates long strings with an ellipsis", () => {
    expect(truncate("abcdefghijk", 10)).toBe("abcdefghi…");
  });
});
