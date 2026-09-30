// @vitest-environment happy-dom
import { cleanup, render, screen } from "@testing-library/react";
import { useTranslations } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IntlProvider } from "./intl-provider";

afterEach(cleanup);

function Probe({ path }: { path: string }) {
  const t = useTranslations();
  return <p data-testid="out">{t(path)}</p>;
}

function renderProbe(path: string, messages: Record<string, unknown> = {}) {
  return render(
    <IntlProvider locale="en" messages={messages} timeZone="Asia/Colombo">
      <Probe path={path} />
    </IntlProvider>,
  );
}

describe("IntlProvider", () => {
  it("renders a present message unchanged", () => {
    renderProbe("greeting", { greeting: "Hello" });
    expect(screen.getByTestId("out").textContent).toBe("Hello");
  });

  it("shows readable text, not the raw key, when a message is missing", () => {
    const report = vi.spyOn(console, "error").mockImplementation(() => undefined);
    renderProbe("gazette.unresolvedReason.NO_FACT");
    const text = screen.getByTestId("out").textContent ?? "";
    expect(text).toBe("No fact");
    expect(text).not.toContain("gazette.");
    // The gap is still reported so it gets fixed.
    expect(report).toHaveBeenCalled();
    report.mockRestore();
  });
});
