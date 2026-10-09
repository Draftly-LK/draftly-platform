// @vitest-environment happy-dom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { WorkflowScreen } from "@/components/workflow/workflow-screen";
import { MissingDocumentsScreen } from "./missing-documents-screen";
import { RequirementsPanel } from "./requirements-panel";
import requirementPacket from "@/test/fixtures/requirement-readiness.json";
import { CheckScopeSelector } from "@/components/checks/check-scope-selector";
import type { ApiChecklist, ApiReadiness } from "@/types/rta";
import type { RunChecksBody } from "@/lib/api/checks";
const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  version: 2,
  scope: null as RunChecksBody | null,
  issueStates: [] as string[],
  readiness: null as ApiReadiness | null,
  checklist: null as ApiChecklist | null,
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
}));
vi.mock("@/lib/store", () => ({
  useDemoStore: () => {
    throw new Error("Live route touched demo store");
  },
}));
vi.mock("@/lib/api/client", async (original) => ({
  ...(await original<Record<string, unknown>>()),
  isApiEnabled: () => true,
}));
vi.mock("@/lib/api/use-token-provider", () => {
  const token = async () => "synthetic";
  return { useTokenProvider: () => token };
});
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("@/lib/api/requirements", () => ({
  listRequirementLinks: async () => [],
  getReadiness: async () => {
    if (mocks.readiness) return mocks.readiness;
    throw new Error("synthetic unavailable");
  },
}));
vi.mock("@/lib/api/matters", () => ({
  getChecklist: async () => mocks.checklist,
  getMatter: async () => ({
    subtypeId: null,
    state: "EVIDENCE_COLLECTION",
    automationScope: "V0_AUTOMATED",
    partyContexts: [],
    activatedConditionalModuleIds: [],
  }),
}));
vi.mock("@/lib/api/documents", () => ({
  getCompleteDocumentInbox: async () => ({
    documents: [],
    sourceFiles: [],
    unprocessedSourceFileIds: [],
  }),
}));
vi.mock("@/lib/api/checks", () => ({
  listCompleteIssues: async () => ({
    items: mocks.issueStates.map((state) => ({ state })),
    page: { hasMore: false },
  }),
}));
vi.mock("@/lib/api/drafts", () => ({
  listForms: async () => ({ items: [], page: { hasMore: false } }),
}));
vi.mock("@/lib/api/facts", () => ({
  listMatterFacts: async () => ({ items: [], page: { hasMore: true } }),
  listTransactions: async () => ({
    items: [
      {
        id: "tx",
        ordinal: 2,
        version: mocks.version,
        parcelSubjectIds: ["parcel"],
        partyRoles: [],
      },
    ],
    page: { nextCursor: null },
  }),
  listSubjects: async () => ({
    items: [{ id: "parcel", ordinal: 7, kind: "parcel" }],
    page: { nextCursor: null },
  }),
}));
beforeEach(() => {
  mocks.version = 2;
  mocks.scope = null;
  mocks.issueStates = [];
  mocks.readiness = null;
  mocks.checklist = null;
  mocks.replace.mockClear();
});
it("redirects legacy live routes without selecting demo state", async () => {
  const first = renderWithIntl(<WorkflowScreen matterId="synthetic" />);
  await waitFor(() =>
    expect(mocks.replace).toHaveBeenCalledWith("/matters/synthetic/checks"),
  );
  first.unmount();
  renderWithIntl(<MissingDocumentsScreen matterId="synthetic" />);
  await waitFor(() =>
    expect(mocks.replace).toHaveBeenCalledWith("/matters/synthetic/documents"),
  );
});
it("requires explicit scope and clears the old association pin on deliberate refresh", async () => {
  const token = async () => "synthetic";
  function Scope() {
    const [scope, setScope] = useState<RunChecksBody | null>(null);
    mocks.scope = scope;
    return (
      <CheckScopeSelector
        matterId="synthetic"
        getToken={token}
        value={scope}
        onChange={setScope}
      />
    );
  }
  renderWithIntl(<Scope />);
  await screen.findByRole("option", { name: "Transaction 2" });
  expect(mocks.scope).toBeNull();
  fireEvent.change(screen.getByLabelText("Transaction"), {
    target: { value: "tx" },
  });
  fireEvent.change(screen.getByLabelText("Subject"), {
    target: { value: "parcel" },
  });
  expect(mocks.scope).toEqual({
    transactionId: "tx",
    subjectId: "parcel",
    associationVersion: 2,
  });
  expect(screen.getByRole("option", { name: /Parcel 7/ })).toBeTruthy();
  mocks.version = 3;
  fireEvent.click(screen.getByRole("button", { name: "Review current scope" }));
  expect(mocks.scope).toBeNull();
  await waitFor(() =>
    expect(screen.getByLabelText("Transaction")).toHaveProperty("value", ""),
  );
  fireEvent.change(screen.getByLabelText("Transaction"), {
    target: { value: "tx" },
  });
  await waitFor(() => expect(mocks.scope?.associationVersion).toBe(3));
});

it.each(["original", "review"] as const)(
  "shows real backend %s work in human controls without relinking",
  async (condition) => {
    const packet = requirementPacket[condition];
    mocks.readiness = packet.readiness as ApiReadiness;
    mocks.checklist = packet.checklist as ApiChecklist;
    const token = async () => "synthetic-token";
    renderWithIntl(
      <RequirementsPanel
        matterId="mat_synthetic"
        getToken={token}
        mode="checks"
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", {
        name: /Original title certificate/i,
      }),
    );
    expect(
      screen.getByRole("button", { name: "Record original inspection" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Record requirement decision" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Link document" })).toBeNull();
  },
);
