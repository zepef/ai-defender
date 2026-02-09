import { describe, expect, it } from "vitest";
import { cn, truncate, duration } from "@/lib/utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("px-2", "py-1")).toBe("px-2 py-1");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "extra")).toBe("base extra");
  });

  it("deduplicates tailwind conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});

describe("truncate", () => {
  it("returns string unchanged when shorter than max", () => {
    expect(truncate("hello", 10)).toBe("hello");
  });

  it("returns string unchanged when exactly max length", () => {
    expect(truncate("hello", 5)).toBe("hello");
  });

  it("truncates and adds ellipsis when longer than max", () => {
    expect(truncate("hello world", 5)).toBe("hello...");
  });

  it("handles empty string", () => {
    expect(truncate("", 5)).toBe("");
  });

  it("handles max of zero", () => {
    expect(truncate("hello", 0)).toBe("...");
  });
});

describe("duration", () => {
  it("formats seconds", () => {
    const start = "2025-01-01T00:00:00Z";
    const end = "2025-01-01T00:00:45Z";
    expect(duration(start, end)).toBe("45s");
  });

  it("formats minutes and seconds", () => {
    const start = "2025-01-01T00:00:00Z";
    const end = "2025-01-01T00:05:30Z";
    expect(duration(start, end)).toBe("5m 30s");
  });

  it("formats hours and minutes", () => {
    const start = "2025-01-01T00:00:00Z";
    const end = "2025-01-01T02:15:00Z";
    expect(duration(start, end)).toBe("2h 15m");
  });

  it("formats zero duration", () => {
    const ts = "2025-01-01T00:00:00Z";
    expect(duration(ts, ts)).toBe("0s");
  });

  it("handles exactly 60 seconds", () => {
    const start = "2025-01-01T00:00:00Z";
    const end = "2025-01-01T00:01:00Z";
    expect(duration(start, end)).toBe("1m 0s");
  });

  it("handles exactly 60 minutes", () => {
    const start = "2025-01-01T00:00:00Z";
    const end = "2025-01-01T01:00:00Z";
    expect(duration(start, end)).toBe("1h 0m");
  });
});
