import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EscalationBadge } from "@/components/escalation-badge";

describe("EscalationBadge", () => {
  it("renders level 0 with label None", () => {
    render(<EscalationBadge level={0} />);
    expect(screen.getByText("0 - None")).toBeDefined();
  });

  it("renders level 1 with label Low", () => {
    render(<EscalationBadge level={1} />);
    expect(screen.getByText("1 - Low")).toBeDefined();
  });

  it("renders level 2 with label Medium", () => {
    render(<EscalationBadge level={2} />);
    expect(screen.getByText("2 - Medium")).toBeDefined();
  });

  it("renders level 3 with label High", () => {
    render(<EscalationBadge level={3} />);
    expect(screen.getByText("3 - High")).toBeDefined();
  });

  it("falls back to level 0 config for unknown levels", () => {
    render(<EscalationBadge level={99} />);
    expect(screen.getByText("99 - None")).toBeDefined();
  });
});
