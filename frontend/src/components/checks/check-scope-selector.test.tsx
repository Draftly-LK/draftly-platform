// @vitest-environment happy-dom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { useState } from "react";
import { renderWithIntl } from "@/test/render";
import type { RunChecksBody } from "@/lib/api/checks";
import { CheckScopeSelector } from "./check-scope-selector";
const mocks = vi.hoisted(() => ({ deferred: null as null | Promise<unknown> }));
vi.mock("@/lib/api/facts", () => ({
  listTransactions: async () => {
    if (mocks.deferred) await mocks.deferred;
    return {
      items: [
        {
          id: "tx",
          ordinal: 1,
          version: 1,
          parcelSubjectIds: [],
          partyRoles: [],
        },
      ],
      page: { nextCursor: null },
    };
  },
  listSubjects: async () => ({ items: [], page: { nextCursor: null } }),
}));
vi.mock("@/components/matter/fact-input", () => ({
  FactScopeInput: () => <p>Shared setup editor</p>,
}));
const token = async () => "synthetic-token";
function Harness() {
  const [scope, setScope] = useState<RunChecksBody | null>(null);
  return (
    <>
      <CheckScopeSelector
        matterId="matter"
        getToken={token}
        value={scope}
        onChange={setScope}
      />
      <button disabled={!scope}>Run synthetic checks</button>
    </>
  );
}
beforeEach(() => {
  mocks.deferred = null;
});
it("disables running while scope reloads and clears the reviewed selection", async () => {
  renderWithIntl(<Harness />);
  await waitFor(() =>
    expect(screen.getByRole("option", { name: "Transaction 1" })).toBeTruthy(),
  );
  fireEvent.change(screen.getByLabelText("Transaction"), {
    target: { value: "tx" },
  });
  await waitFor(() =>
    expect(
      (
        screen.getByRole("button", {
          name: "Run synthetic checks",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false),
  );
  let finish!: () => void;
  mocks.deferred = new Promise((resolve) => {
    finish = () => resolve(undefined);
  });
  fireEvent.click(screen.getByRole("button", { name: "Review current scope" }));
  expect(
    (screen.getByLabelText("Transaction") as HTMLSelectElement).disabled,
  ).toBe(true);
  expect(
    (
      screen.getByRole("button", {
        name: "Run synthetic checks",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  finish();
  await waitFor(() =>
    expect(
      (screen.getByLabelText("Transaction") as HTMLSelectElement).disabled,
    ).toBe(false),
  );
  expect(
    (screen.getByLabelText("Transaction") as HTMLSelectElement).value,
  ).toBe("");
});
it("offers the shared setup editor directly", async () => {
  renderWithIntl(<Harness />);
  expect(await screen.findByText("Shared setup editor")).toBeTruthy();
});
