// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  checkLabels,
  physicalOriginalLabels,
  sourceFileStateLabels,
  stepLabels,
  verificationLabels,
} from "@/lib/i18n/labels";
import { renderWithIntl } from "@/test/render";
import { StatusBadge } from "./status-badge";

type Status = Parameters<typeof StatusBadge>[0]["status"];

// Every status the badge accepts, with the label it must print.
const EVERY_STATUS = Object.entries({
  ...verificationLabels,
  ...sourceFileStateLabels,
  ...physicalOriginalLabels,
  ...checkLabels,
  ...stepLabels,
}) as [Status, { en: string; si: string }][];

describe("StatusBadge", () => {
  it.each(EVERY_STATUS)("%s shows an icon and its text label, never colour alone", (status, label) => {
    const { container } = renderWithIntl(<StatusBadge status={status} />);

    const badge = container.querySelector(`[data-status="${status}"]`);
    expect(badge?.textContent).toBe(label.en);
    expect(badge?.querySelector("svg[aria-hidden='true']")).not.toBeNull();
  });

  it("uses the Sinhala label in the Sinhala locale", () => {
    renderWithIntl(<StatusBadge status="verified" />, "si");

    expect(screen.getByText(verificationLabels.verified.si)).toBeTruthy();
  });

  it("keeps a caller's extra class alongside its own", () => {
    const { container } = renderWithIntl(<StatusBadge status="pass" className="synthetic-class" />);

    expect(container.firstElementChild?.className).toContain("synthetic-class");
    expect(container.firstElementChild?.className).toContain("rounded-full");
  });
});
