import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock next/link to render a plain <a> tag
vi.mock("next/link", () => ({
  default: ({ children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a {...props}>{children}</a>,
}));

// Mock next/navigation with a controllable pathname
let mockPathname = "/";
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

import { Sidebar } from "@/components/sidebar";

describe("Sidebar", () => {
  it("renders all nav items", () => {
    mockPathname = "/";
    render(<Sidebar />);
    expect(screen.getByText("Overview")).toBeDefined();
    expect(screen.getByText("Sessions")).toBeDefined();
    expect(screen.getByText("Tokens")).toBeDefined();
  });

  it('marks Overview as active when pathname is "/"', () => {
    mockPathname = "/";
    render(<Sidebar />);
    const overviewLink = screen.getByText("Overview");
    expect(overviewLink.getAttribute("aria-current")).toBe("page");
  });

  it("marks Sessions as active when pathname starts with /sessions", () => {
    mockPathname = "/sessions";
    render(<Sidebar />);
    const sessionsLink = screen.getByText("Sessions");
    expect(sessionsLink.getAttribute("aria-current")).toBe("page");
    // Overview should NOT be active
    const overviewLink = screen.getByText("Overview");
    expect(overviewLink.getAttribute("aria-current")).toBeNull();
  });

  it("marks Tokens as active when pathname starts with /tokens", () => {
    mockPathname = "/tokens";
    render(<Sidebar />);
    const tokensLink = screen.getByText("Tokens");
    expect(tokensLink.getAttribute("aria-current")).toBe("page");
  });

  it("renders the hamburger toggle button", () => {
    mockPathname = "/";
    render(<Sidebar />);
    const toggleBtn = screen.getByRole("button", { name: "Toggle navigation" });
    expect(toggleBtn).toBeDefined();
    expect(toggleBtn.getAttribute("aria-expanded")).toBe("false");
  });

  it("renders the application title", () => {
    mockPathname = "/";
    render(<Sidebar />);
    expect(screen.getByText("AI-Defender")).toBeDefined();
  });
});
