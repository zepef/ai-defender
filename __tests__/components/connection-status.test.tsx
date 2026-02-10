import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock the event stream context
const mockUseEventStreamContext = vi.fn();
vi.mock("@/lib/event-stream-context", () => ({
  useEventStreamContext: () => mockUseEventStreamContext(),
}));

import { ConnectionStatus } from "@/components/connection-status";

describe("ConnectionStatus", () => {
  it("renders Live when connected", () => {
    mockUseEventStreamContext.mockReturnValue({
      connected: true,
      error: null,
    });
    render(<ConnectionStatus />);
    expect(screen.getByText("Live")).toBeDefined();
  });

  it("renders Disconnected when not connected and no error", () => {
    mockUseEventStreamContext.mockReturnValue({
      connected: false,
      error: null,
    });
    render(<ConnectionStatus />);
    expect(screen.getByText("Disconnected")).toBeDefined();
  });

  it("renders error message when disconnected with error", () => {
    mockUseEventStreamContext.mockReturnValue({
      connected: false,
      error: "Connection lost. Retrying in 2s...",
    });
    render(<ConnectionStatus />);
    expect(screen.getByText("Connection lost. Retrying in 2s...")).toBeDefined();
  });

  it("renders green dot when connected", () => {
    mockUseEventStreamContext.mockReturnValue({
      connected: true,
      error: null,
    });
    const { container } = render(<ConnectionStatus />);
    const dot = container.querySelector("span[aria-hidden]");
    expect(dot?.className).toContain("bg-green-500");
  });

  it("renders red dot when disconnected", () => {
    mockUseEventStreamContext.mockReturnValue({
      connected: false,
      error: null,
    });
    const { container } = render(<ConnectionStatus />);
    const dot = container.querySelector("span[aria-hidden]");
    expect(dot?.className).toContain("bg-red-500");
  });
});
