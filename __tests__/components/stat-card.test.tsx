import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatCard } from "@/components/stat-card";

describe("StatCard", () => {
  it("renders the title", () => {
    render(<StatCard title="Active Sessions" value={42} />);
    expect(screen.getByText("Active Sessions")).toBeDefined();
  });

  it("renders a string value", () => {
    render(<StatCard title="Status" value="Healthy" />);
    expect(screen.getByText("Healthy")).toBeDefined();
  });

  it("renders a numeric value", () => {
    render(<StatCard title="Threats Detected" value={128} />);
    expect(screen.getByText("128")).toBeDefined();
  });
});
