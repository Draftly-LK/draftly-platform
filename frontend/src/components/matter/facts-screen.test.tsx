// @vitest-environment happy-dom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DEMO_GAZETTE_FORMS } from "@/lib/gazette-forms/demo-forms";
import { fieldStatus, printedValue } from "@/lib/gazette-forms/field-state";
import { renderWithIntl } from "@/test/render";
import type { ApiGeneratedForm } from "@/types/rta";

const recordFieldDecision = vi.fn();

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  isApiEnabled: () => true,
}));
vi.mock("@/lib/api/use-token-provider", () => ({ useTokenProvider: () => async () => "token" }));
vi.mock("@/lib/api/checks", () => ({ listCheckResults: async () => ({ items: [] }) }));
vi.mock("@/lib/api/drafts", () => ({
  listForms: async () => ({ items: [{ id: "form-1" }] }),
  getForm: async () => form,
  recordFieldDecision: (...args: unknown[]) => recordFieldDecision(...args),
}));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const source = DEMO_GAZETTE_FORMS[0]!;
let form: ApiGeneratedForm;

import { FactsScreen } from "./facts-screen";

describe("facts screen corrections", () => {
  beforeEach(() => {
    recordFieldDecision.mockReset();
    form = { ...source, id: "form-1", state: "UNRESOLVED" };
  });

  it("lets a lawyer open a fact and record a decision on it", async () => {
    const facts = form.fields.filter((f) => f.factId !== null);
    const index = facts.findIndex((f) => printedValue(f) !== null && fieldStatus(f) !== "confirmed");
    if (index === -1) throw new Error("fixture has no fact awaiting confirmation");
    recordFieldDecision.mockResolvedValue(form);

    renderWithIntl(<FactsScreen matterId="matter-1" />);
    const buttons = await screen.findAllByRole("button", { name: "Review or correct" });
    fireEvent.click(buttons[index]!);
    expect(await screen.findByRole("button", { name: "Close" })).toBeTruthy();

    fireEvent.click(await screen.findByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(recordFieldDecision).toHaveBeenCalledTimes(1));
    expect(recordFieldDecision.mock.calls[0]![2]).toMatchObject({
      fieldId: facts[index]!.fieldId,
      action: "CONFIRM",
    });
    expect(recordFieldDecision.mock.calls[0]![3]).toBe(form.version);
  });

  it("makes the rows view-only once the form is approved", async () => {
    form = { ...form, state: "APPROVED" };
    renderWithIntl(<FactsScreen matterId="matter-1" />);
    const buttons = await screen.findAllByRole("button", { name: "View" });
    fireEvent.click(buttons[0]!);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull());
    expect(recordFieldDecision).not.toHaveBeenCalled();
  });
});
