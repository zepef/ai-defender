import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BarIndicator } from "@/components/bar-indicator";

describe("BarIndicator", () => {
  it("renders the label", () => {
    render(<BarIndicator label="Requests" value={50} max={100} />);
    expect(screen.getByText("Requests")).toBeDefined();
  });

  it("renders the numeric value", () => {
    render(<BarIndicator label="Requests" value={50} max={100} />);
    expect(screen.getByText("50")).toBeDefined();
  });

  it("has correct aria attributes on the progressbar", () => {
    render(<BarIndicator label="Requests" value={30} max={200} />);
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar.getAttribute("aria-label")).toBe("Requests");
    expect(progressbar.getAttribute("aria-valuenow")).toBe("30");
    expect(progressbar.getAttribute("aria-valuemin")).toBe("0");
    expect(progressbar.getAttribute("aria-valuemax")).toBe("200");
  });

  it("handles max=0 by setting width to 0%", () => {
    render(<BarIndicator label="Empty" value={10} max={0} />);
    const progressbar = screen.getByRole("progressbar");
    const innerBar = progressbar.firstElementChild as HTMLElement;
    expect(innerBar.style.width).toBe("0%");
  });

  it("computes percentage correctly", () => {
    render(<BarIndicator label="CPU" value={75} max={100} />);
    const progressbar = screen.getByRole("progressbar");
    const innerBar = progressbar.firstElementChild as HTMLElement;
    expect(innerBar.style.width).toBe("75%");
  });

  it("rounds percentage to nearest integer", () => {
    render(<BarIndicator label="Memory" value={1} max={3} />);
    const progressbar = screen.getByRole("progressbar");
    const innerBar = progressbar.firstElementChild as HTMLElement;
    // 1/3 = 0.333... => Math.round(33.33) = 33
    expect(innerBar.style.width).toBe("33%");
  });
});
