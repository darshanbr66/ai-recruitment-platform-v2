import { describe, expect, it } from "vitest";
import { avatarStyle, initials } from "./avatar";

describe("initials", () => {
  it("uses first and last name initials", () => {
    expect(initials("Riya Recruiter")).toBe("RR");
    expect(initials("  ada   king lovelace ")).toBe("AL");
  });

  it("handles a single name and missing names", () => {
    expect(initials("Madonna")).toBe("M");
    expect(initials("")).toBe("?");
    expect(initials(null)).toBe("?");
    expect(initials(undefined)).toBe("?");
  });
});

describe("avatarStyle", () => {
  it("keeps the same tone for the same person, regardless of case", () => {
    expect(avatarStyle("Riya Recruiter")).toEqual(avatarStyle("riya recruiter"));
  });

  it("only ever uses theme tokens (never a hard-coded colour)", () => {
    for (const name of ["A", "Bo", "Cy Dee", "Eve Fox", "Gus"]) {
      const style = avatarStyle(name) as Record<string, string>;
      expect(style["--avatar-bg"]).toMatch(/^var\(--color-/);
      expect(style["--avatar-fg"]).toMatch(/^var\(--color-/);
    }
  });
});
