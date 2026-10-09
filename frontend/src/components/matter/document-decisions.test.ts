import { describe, expect, it } from "vitest";
import type { ApiDetectedDocument } from "@/types/rta";
import { isDocumentDecided } from "./document-decisions";

describe("document completion", () => {
  it.each(["refresh_required", "failed", "unsupported", undefined])(
    "withholds completion while extraction is %s",
    (extractionState) => {
      expect(
        isDocumentDecided({
          classStatus: "LAWYER_CONFIRMED",
          boundaryStatus: "CONFIRMED",
          extractionState,
        } as ApiDetectedDocument),
      ).toBe(false);
    },
  );
  it("requires the current extraction as well as both lawyer decisions", () => {
    expect(
      isDocumentDecided({
        classStatus: "LAWYER_CONFIRMED",
        boundaryStatus: "CONFIRMED",
        extractionState: "current",
      } as ApiDetectedDocument),
    ).toBe(true);
  });
});
