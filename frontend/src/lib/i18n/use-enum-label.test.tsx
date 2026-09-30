// @vitest-environment happy-dom
import { renderHook } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import en from "./messages/en.json";
import { useEnumLabel } from "./use-enum-label";

const wrapper = ({ children }: { children: ReactNode }) => (
  <NextIntlClientProvider locale="en" messages={en} timeZone="Asia/Colombo">
    {children}
  </NextIntlClientProvider>
);

describe("useEnumLabel", () => {
  it("uses the catalogue label when there is one", () => {
    const { result } = renderHook(() => useEnumLabel("enums.sourceFileState"), { wrapper });
    expect(result.current("PROCESSING_FAILED")).toBe("Processing failed");
  });

  it("humanises a value the catalogue does not know, without reporting an error", () => {
    const { result } = renderHook(() => useEnumLabel("enums.sourceFileState"), { wrapper });
    expect(result.current("BRAND_NEW_STATE")).toBe("Brand new state");
  });

  it("returns an empty string for a missing value", () => {
    const { result } = renderHook(() => useEnumLabel("enums.factStatus"), { wrapper });
    expect(result.current(null)).toBe("");
    expect(result.current(undefined)).toBe("");
  });
});
