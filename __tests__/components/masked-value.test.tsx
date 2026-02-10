import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MaskedValue } from "@/components/masked-value";

describe("MaskedValue", () => {
  it("renders masked by default", () => {
    render(<MaskedValue value="secret-token-123" />);
    expect(screen.queryByText("secret-token-123")).toBeNull();
    expect(screen.getByText("show")).toBeDefined();
  });

  it("reveals value when show is clicked", () => {
    render(<MaskedValue value="secret-token-123" />);
    fireEvent.click(screen.getByText("show"));
    expect(screen.getByText("secret-token-123")).toBeDefined();
    expect(screen.getByText("hide")).toBeDefined();
  });

  it("hides value again when hide is clicked", () => {
    render(<MaskedValue value="secret-token-123" />);
    fireEvent.click(screen.getByText("show"));
    fireEvent.click(screen.getByText("hide"));
    expect(screen.queryByText("secret-token-123")).toBeNull();
    expect(screen.getByText("show")).toBeDefined();
  });

  it("has accessible labels on the toggle button", () => {
    render(<MaskedValue value="test" />);
    const btn = screen.getByRole("button");
    expect(btn.getAttribute("aria-label")).toBe("Reveal value");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-label")).toBe("Hide value");
  });
});
