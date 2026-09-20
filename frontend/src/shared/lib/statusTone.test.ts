import { describe, expect, it } from "vitest";
import { humanizeStatus, statusTone, toneBadgeClass, toneColor } from "./statusTone";

describe("statusTone", () => {
  it("gives every pipeline stage a stable, meaningful tone", () => {
    expect(statusTone("APPLIED")).toBe("neutral");
    expect(statusTone("SCREENING")).toBe("info");
    expect(statusTone("INTERVIEW")).toBe("brand");
    expect(statusTone("SELECTED")).toBe("success");
    expect(statusTone("REJECTED")).toBe("danger");
    expect(statusTone("HIRED")).toBe("accent"); // the human success gets the warm accent
  });

  it("falls back to neutral for an unknown stage rather than guessing", () => {
    expect(statusTone("SOMETHING_NEW")).toBe("neutral");
  });

  it("maps tones to badge classes and theme-aware colours", () => {
    expect(toneBadgeClass("danger")).toBe("badge badge-danger");
    expect(toneBadgeClass(statusTone("HIRED"))).toBe("badge badge-accent");
    expect(toneColor("success")).toMatch(/^var\(--/);
  });

  it("humanizes stage names", () => {
    expect(humanizeStatus("UNDER_REVIEW")).toBe("Under review");
    expect(humanizeStatus("HIRED")).toBe("Hired");
  });
});
