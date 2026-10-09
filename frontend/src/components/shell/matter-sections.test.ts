import { describe, expect, it } from "vitest";
import {
  MATTER_SECTIONS,
  matterSectionHref,
  sectionForPath,
} from "./matter-sections";

describe("matter sections", () => {
  it("gives the checklist a dedicated tab immediately after overview", () => {
    expect(MATTER_SECTIONS.slice(0, 2)).toEqual(["overview", "checklist"]);
    expect(sectionForPath("/matters/m1/checklist", "m1")).toBe("checklist");
    expect(sectionForPath("/matters/other/checklist", "m1")).toBeNull();
    const checklist = MATTER_SECTIONS.find(
      (section) => String(section) === "checklist",
    );
    expect(checklist && matterSectionHref(checklist, "m1")).toBe(
      "/matters/m1/checklist",
    );
  });
  it("files a sub-page under its section, and the overview only on its own path", () => {
    expect(sectionForPath("/matters/m1", "m1")).toBe("overview");
    expect(sectionForPath("/matters/m1/documents/d1/review", "m1")).toBe(
      "documents",
    );
    expect(sectionForPath("/matters/other/facts", "m1")).toBeNull();
    expect(sectionForPath("/matters/m1/workflow", "m1")).toBe("checks");
    expect(sectionForPath("/matters/m1/missing-documents", "m1")).toBe(
      "documents",
    );
  });
});
