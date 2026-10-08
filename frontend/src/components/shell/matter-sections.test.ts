import { describe, expect, it } from "vitest";
import { sectionForPath } from "./matter-sections";

describe("matter sections", () => {
  it("files a sub-page under its section, and the overview only on its own path", () => {
    expect(sectionForPath("/matters/m1", "m1")).toBe("overview");
    expect(sectionForPath("/matters/m1/documents/d1/review", "m1")).toBe("documents");
    expect(sectionForPath("/matters/other/facts", "m1")).toBeNull();
  });
});
