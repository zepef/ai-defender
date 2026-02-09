import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RelativeTime } from "@/components/relative-time";

describe("RelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Fix "now" to a known timestamp: 2026-01-15T12:00:00.000Z
    vi.setSystemTime(new Date("2026-01-15T12:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders "just now" for timestamps less than 60 seconds ago', () => {
    const iso = new Date("2026-01-15T11:59:30.000Z").toISOString(); // 30s ago
    render(<RelativeTime iso={iso} />);
    expect(screen.getByText("just now")).toBeDefined();
  });

  it('renders "Xm ago" for timestamps minutes ago', () => {
    const iso = new Date("2026-01-15T11:45:00.000Z").toISOString(); // 15m ago
    render(<RelativeTime iso={iso} />);
    expect(screen.getByText("15m ago")).toBeDefined();
  });

  it('renders "Xh ago" for timestamps hours ago', () => {
    const iso = new Date("2026-01-15T09:00:00.000Z").toISOString(); // 3h ago
    render(<RelativeTime iso={iso} />);
    expect(screen.getByText("3h ago")).toBeDefined();
  });

  it('renders "Xd ago" for timestamps days ago', () => {
    const iso = new Date("2026-01-13T12:00:00.000Z").toISOString(); // 2d ago
    render(<RelativeTime iso={iso} />);
    expect(screen.getByText("2d ago")).toBeDefined();
  });

  it("has the correct dateTime attribute on the <time> element", () => {
    const iso = "2026-01-15T11:50:00.000Z";
    render(<RelativeTime iso={iso} />);
    const timeEl = screen.getByText("10m ago");
    expect(timeEl.tagName).toBe("TIME");
    expect(timeEl.getAttribute("dateTime")).toBe(iso);
  });
});
