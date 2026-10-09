// @vitest-environment happy-dom
import { useState } from "react";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import en from "@/lib/i18n/messages/en.json";
import si from "@/lib/i18n/messages/si.json";
import type {
  ApiFormScope,
  ApiMatterSubject,
  ApiMatterTransaction,
} from "@/types/rta";
import { FormScopeSelector } from "./form-scope-selector";

const reads = vi.hoisted(() => ({ transactions: vi.fn(), subjects: vi.fn() }));
vi.mock("@/lib/api/facts", () => ({
  listTransactions: reads.transactions,
  listSubjects: reads.subjects,
}));
const token = async () => "synthetic-token";
const page = { limit: 100, hasMore: false, nextCursor: null };
const transaction: ApiMatterTransaction = {
  id: "tx-1",
  matterId: "mat-1",
  userId: "synthetic-actor",
  ordinal: 1,
  version: 3,
  partyRoles: [
    { subjectId: "party-1", role: "transferor" },
    { subjectId: "party-2", role: "transferee" },
  ],
  parcelSubjectIds: ["parcel-1"],
};
const subjects: ApiMatterSubject[] = [
  {
    id: "party-1",
    matterId: "mat-1",
    userId: "synthetic-actor",
    kind: "party",
    ordinal: 1,
  },
  {
    id: "party-2",
    matterId: "mat-1",
    userId: "synthetic-actor",
    kind: "party",
    ordinal: 2,
  },
  {
    id: "parcel-1",
    matterId: "mat-1",
    userId: "synthetic-actor",
    kind: "parcel",
    ordinal: 1,
  },
];
function Harness() {
  const [scope, setScope] = useState<ApiFormScope | null>(null);
  return (
    <>
      <FormScopeSelector
        matterId="mat-1"
        getToken={token}
        value={scope}
        onChange={setScope}
      />
      <output aria-label="Selected scope">{JSON.stringify(scope)}</output>
    </>
  );
}
beforeEach(() => {
  reads.transactions
    .mockReset()
    .mockResolvedValue({ items: [transaction], page });
  reads.subjects.mockReset().mockResolvedValue({ items: subjects, page });
});
describe("draft transaction setup", () => {
  it("announces loading without claiming there are no transactions", async () => {
    let finish!: (value: unknown) => void;
    reads.transactions.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    renderWithIntl(<Harness />);
    expect(screen.getByText(en.formScope.loading).getAttribute("role")).toBe(
      "status",
    );
    expect(screen.queryByText(/No transaction associations/)).toBeNull();
    finish({ items: [], page });
    await screen.findByRole("link", {
      name: "Set up transaction",
    });
  });
  it("offers transaction setup instead of empty selectors for a successful empty read", async () => {
    reads.transactions.mockResolvedValue({ items: [], page });
    renderWithIntl(<Harness />);
    const setup = await screen.findByRole("link", {
      name: "Set up transaction",
    });
    expect(setup.getAttribute("href")).toBe(
      "/matters/mat-1/facts#transaction-scope",
    );
    expect(screen.getByText(/No transaction associations/)).toBeTruthy();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByLabelText("Selected scope").textContent).toBe("null");
  });
  it.each(["en", "si"] as const)(
    "localizes setup guidance in %s",
    async (locale) => {
      reads.transactions.mockResolvedValue({ items: [], page });
      renderWithIntl(<Harness />, locale);
      const catalogue = locale === "en" ? en : si;
      expect(await screen.findByText(catalogue.formScope.empty)).toBeTruthy();
      expect(
        screen
          .getByRole("link", { name: catalogue.formScope.setup })
          .getAttribute("href"),
      ).toBe("/matters/mat-1/facts#transaction-scope");
    },
  );
  it("includes later signed transaction pages without choosing one", async () => {
    reads.transactions
      .mockResolvedValueOnce({
        items: [],
        page: { ...page, hasMore: true, nextCursor: "synthetic-next" },
      })
      .mockResolvedValue({ items: [transaction], page });
    renderWithIntl(<Harness />);
    await screen.findByRole("option", { name: "Transaction 1" });
    expect(screen.getByLabelText("Selected scope").textContent).toBe("null");
  });
  it("refuses repeated cursors rather than presenting incomplete transactions", async () => {
    reads.transactions.mockResolvedValue({
      items: [],
      page: { ...page, hasMore: true, nextCursor: "synthetic-repeated" },
    });
    renderWithIntl(<Harness />);
    await screen.findByRole("alert");
    expect(screen.queryByRole("combobox")).toBeNull();
  });
  it("withholds transactions whose associated subjects are unavailable", async () => {
    reads.subjects.mockResolvedValue({ items: [], page });
    renderWithIntl(<Harness />);
    await screen.findByRole("alert");
    expect(screen.queryByRole("combobox")).toBeNull();
  });
  it("distinguishes unavailable scope from an empty account and offers reload", async () => {
    reads.transactions.mockRejectedValue(new Error("Synthetic unavailable"));
    renderWithIntl(<Harness />);
    await screen.findByRole("alert");
    expect(screen.queryByText(/No transaction associations/)).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    reads.transactions.mockResolvedValue({ items: [transaction], page });
    fireEvent.click(screen.getByRole("button", { name: "Reload scope" }));
    await screen.findByRole("option", { name: "Transaction 1" });
  });
  it.each(["transactions", "subjects"] as const)(
    "withholds a %s list with hasMore but no cursor",
    async (kind) => {
      reads[kind].mockResolvedValue({
        items: kind === "transactions" ? [transaction] : subjects,
        page: { ...page, hasMore: true },
      });
      renderWithIntl(<Harness />);
      await screen.findByRole("alert");
      expect(screen.queryByRole("combobox")).toBeNull();
      expect(screen.getByLabelText("Selected scope").textContent).toBe("null");
    },
  );
  it("requires explicit transaction and subject selection and pins its displayed version", async () => {
    renderWithIntl(<Harness />);
    await screen.findByRole("option", { name: "Transaction 1" });
    expect(screen.getByLabelText("Selected scope").textContent).toBe("null");
    fireEvent.change(screen.getByLabelText("Transaction"), {
      target: { value: "tx-1" },
    });
    expect(
      JSON.parse(screen.getByLabelText("Selected scope").textContent!),
    ).toEqual({
      transactionId: "tx-1",
      associationVersion: 3,
      parcelSubjectId: null,
      transferorSubjectId: null,
      transfereeSubjectId: null,
    });
    fireEvent.change(screen.getByLabelText("Parcel"), {
      target: { value: "parcel-1" },
    });
    expect(
      JSON.parse(screen.getByLabelText("Selected scope").textContent!)
        .parcelSubjectId,
    ).toBe("parcel-1");
    fireEvent.change(screen.getByLabelText("Transferor"), {
      target: { value: "party-1" },
    });
    fireEvent.change(screen.getByLabelText("Transferee"), {
      target: { value: "party-2" },
    });
    expect(
      JSON.parse(screen.getByLabelText("Selected scope").textContent!),
    ).toEqual({
      transactionId: "tx-1",
      associationVersion: 3,
      parcelSubjectId: "parcel-1",
      transferorSubjectId: "party-1",
      transfereeSubjectId: "party-2",
    });
    fireEvent.change(screen.getByLabelText("Transaction"), {
      target: { value: "" },
    });
    expect(screen.getByLabelText("Selected scope").textContent).toBe("null");
    fireEvent.click(screen.getByRole("button", { name: "Reload scope" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Selected scope").textContent).toBe("null"),
    );
  });
  it("explains missing role associations while allowing a transaction with unresolved subjects", async () => {
    reads.transactions.mockResolvedValue({
      items: [{ ...transaction, partyRoles: [], parcelSubjectIds: [] }],
      page,
    });
    renderWithIntl(<Harness />);
    await screen.findByRole("option", { name: "Transaction 1" });
    fireEvent.change(screen.getByLabelText("Transaction"), {
      target: { value: "tx-1" },
    });
    expect(
      await screen.findByText(
        /This transaction has missing parcel or party role associations/,
      ),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "Set up transaction" })
        .getAttribute("href"),
    ).toBe("/matters/mat-1/facts#transaction-scope");
    expect(
      JSON.parse(screen.getByLabelText("Selected scope").textContent!)
        .transactionId,
    ).toBe("tx-1");
  });
});
