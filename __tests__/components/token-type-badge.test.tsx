import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TokenTypeBadge } from "@/components/token-type-badge";

describe("TokenTypeBadge", () => {
  it.each(["aws", "api", "db", "admin", "ssh"])(
    "renders known type '%s' with its text",
    (type) => {
      render(<TokenTypeBadge type={type} />);
      expect(screen.getByText(type)).toBeDefined();
    }
  );

  it("renders unknown type with fallback styling", () => {
    render(<TokenTypeBadge type="unknown" />);
    const badge = screen.getByText("unknown");
    expect(badge).toBeDefined();
    expect(badge.className).toContain("bg-zinc-800");
  });

  it("displays the type text in uppercase via CSS class", () => {
    render(<TokenTypeBadge type="api" />);
    const badge = screen.getByText("api");
    expect(badge.className).toContain("uppercase");
  });
});
