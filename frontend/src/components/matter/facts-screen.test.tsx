// @vitest-environment happy-dom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { webcrypto } from "node:crypto";
import en from "@/lib/i18n/messages/en.json";
import { renderWithIntl } from "@/test/render";
import type { ApiMatterFact } from "@/types/rta";
import { FactsScreen } from "./facts-screen";
const token = async () => "synthetic-token";
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => token,
}));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
const pageInfo = { limit: 50, hasMore: false, nextCursor: null };
const fact = (overrides: Partial<ApiMatterFact> = {}): ApiMatterFact => ({
  id: "fact-1",
  matterId: "mat-1",
  factTypeId: "rta.party.holder_name_en",
  fieldKey: "holderNameEn",
  labelKey: "rta.fact.holder_name_en",
  value: "SYNTHETIC CURRENT",
  originalValue: "SYNTHETIC ORIGINAL",
  status: "LAWYER_CONFIRMED",
  origin: "machine",
  modelReportedConfidence: 0.81,
  evidence: [
    {
      id: "evidence",
      sourceFileId: "source",
      detectedDocumentId: "doc",
      pageNumber: 1,
      sourceSha256: "a".repeat(64),
      extractionRunId: "run",
      supportingText: "SYNTHETIC ORIGINAL",
      pageText: "SYNTHETIC ORIGINAL page",
      precision: "text",
      candidateId: null,
      candidateVersion: null,
      boundingBox: null,
    },
  ],
  reviewedBy: "synthetic-lawyer",
  reviewedAt: "2026-10-09T00:00:00Z",
  createdAt: "2026-10-09T00:00:00Z",
  version: 2,
  transactionId: "tx-1",
  subjectId: "party-1",
  scopeStatus: "assigned",
  evidenceStale: false,
  sourceCandidateId: null,
  manualReason: null,
  lineageId: "lineage",
  supersedesFactId: null,
  supersededByFactId: null,
  scopeToken: "server-token-2",
  conflictFactIds: [],
  ...overrides,
});
let facts: ApiMatterFact[],
  calls: { path: string; init: RequestInit; body: Record<string, unknown> }[];
let refuse: number, more: boolean;
let brokenCursor: boolean, historyMore: boolean;
let failurePaths: Record<string, number>;
let pending: ((value: Response) => void) | null;
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal("crypto", webcrypto);
  facts = [fact()];
  calls = [];
  refuse = 0;
  more = false;
  brokenCursor = false;
  historyMore = false;
  pending = null;
  failurePaths = {};
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const path = String(input).replace("http://api.test", "");
      const body = init.body ? JSON.parse(String(init.body)) : {};
      calls.push({ path, init, body });
      if (path === "/api/v1/me") return response({ id: "synthetic-lawyer" });
      if (failurePaths[path])
        return response(
          {
            error: {
              code: "synthetic_error",
              message: "Synthetic unavailable",
            },
          },
          failurePaths[path],
        );
      if (path.includes("/mat-OLD/facts"))
        return new Promise<Response>((resolve) => {
          pending = resolve;
        });
      if (path.endsWith("/forms")) return response({ items: [] });
      if (path.endsWith("/checks")) return response({ items: [] });
      if (path.includes("/fact-types"))
        return response({
          versions: { rulePack: "1" },
          factTypes: [
            {
              id: "rta.party.holder_name_en",
              labelKey: "rta.fact.holder_name_en",
              fieldKey: "holderNameEn",
              subject: "PARTY",
              valueKind: "TEXT",
              critical: false,
              negativeRequiresSearchEvidence: false,
            },
            {
              id: "rta.interest.mortgage_status",
              labelKey: "rta.fact.mortgage_status",
              fieldKey: null,
              subject: "INTEREST",
              valueKind: "ENUM",
              critical: true,
              negativeRequiresSearchEvidence: true,
              options: [
                {
                  value: "NOT_FOUND_IN_CURRENT_SEARCH",
                  labelKey:
                    "enums.encumbranceStatus.NOT_FOUND_IN_CURRENT_SEARCH",
                },
              ],
            },
            {
              id: "rta.title.certificate_no",
              labelKey: "rta.fact.certificate_no",
              fieldKey: "titleCertificateNo",
              subject: "TITLE",
              valueKind: "IDENTIFIER",
              critical: true,
              negativeRequiresSearchEvidence: false,
              options: [],
            },
          ],
        });
      if (path.includes("/source-files"))
        return response({
          items: [
            {
              id: "source",
              matterId: "mat-1",
              originalFilename: "Synthetic source.pdf",
              sha256: "a".repeat(64),
              pageCount: 2,
              state: "PROCESSED",
              detectedDocumentIds: ["doc"],
            },
          ],
          page: pageInfo,
        });
      if (path.includes("/subjects"))
        return response({
          items: [
            ...[1, 2].map((n) => ({
              id: `party-${n}`,
              matterId: "mat-1",
              kind: "party",
              ordinal: n,
            })),
            { id: "parcel-1", matterId: "mat-1", kind: "parcel", ordinal: 1 },
          ],
          page: pageInfo,
        });
      if (path.includes("/transactions"))
        return response({
          items: [
            {
              id: "tx-1",
              matterId: "mat-1",
              ordinal: 1,
              version: 1,
              partyRoles: [
                { subjectId: "party-1", role: "owner" },
                { subjectId: "party-2", role: "transferee" },
              ],
              parcelSubjectIds: [],
            },
          ],
          page: pageInfo,
        });
      if (path.includes("/history"))
        return response({
          items: facts,
          decisions: [
            {
              id: path.includes("cursor=") ? "decision-2" : "decision",
              decision: "correct",
              targetId: "fact-1",
              reviewerId: "synthetic-lawyer",
              reviewerRole: "approver",
              createdAt: "2026-10-09T00:00:00Z",
              previousValue: "SYNTHETIC ORIGINAL",
              newValue: "SYNTHETIC CURRENT",
              reason: path.includes("cursor=")
                ? "Synthetic older decision"
                : "Synthetic correction",
              resolvedFactIds: [],
            },
          ],
          page: {
            ...pageInfo,
            hasMore: historyMore && !path.includes("cursor="),
            nextCursor:
              historyMore && !path.includes("cursor=")
                ? "signed-history-2"
                : null,
          },
        });
      if (init.method === "POST") {
        if (refuse) {
          const status = refuse;
          refuse = 0;
          return response(
            {
              error: {
                code:
                  status === 412 ? "precondition_failed" : "capability_denied",
                message: "Synthetic refusal",
                details: { currentFactId: "fact-1" },
              },
            },
            status,
          );
        }
        const prior = facts.find((f) => path.includes(f.id)) ?? facts[0]!;
        const next = fact({
          ...prior,
          id: prior.id + "-next",
          version: prior.version + 1,
          value: (body.value as string) ?? prior.value,
          scopeToken: "returned-token",
          status:
            path.endsWith("/associate") || path.endsWith("/facts")
              ? "REVIEW_REQUIRED"
              : path.endsWith("/reject")
                ? "REJECTED"
                : "LAWYER_CONFIRMED",
          subjectId: (body.subjectId as string) ?? prior.subjectId,
          transactionId: (body.transactionId as string) ?? prior.transactionId,
          scopeStatus: "assigned",
          origin: path.endsWith("/facts") ? "lawyer" : prior.origin,
        });
        facts = [next, ...facts.filter((f) => f.id !== prior.id)];
        return response(next);
      }
      const id = new URL(String(input)).pathname.split("/").at(-1);
      if (id !== "facts" && !path.includes("?cursor="))
        return response(
          facts.find((f) => f.id === id) ??
            fact({ id: id!, value: "SYNTHETIC PEER" }),
        );
      return response({
        items: path.includes("cursor=")
          ? [fact({ id: "page-2", value: "SYNTHETIC NEXT PAGE" })]
          : facts,
        page: {
          ...pageInfo,
          hasMore: brokenCursor || (more && !path.includes("cursor=")),
          nextCursor:
            !brokenCursor && more && !path.includes("cursor=")
              ? "signed-page-2"
              : null,
        },
      });
    }),
  );
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
async function open() {
  fireEvent.click(
    (await screen.findAllByRole("button", { name: "Review or correct" }))[0]!,
  );
  await screen.findByRole("button", { name: "Accept fact" });
}
describe("canonical register", () => {
  it("renders governed enum meanings in current, original and history values", async () => {
    facts = [
      fact({
        factTypeId: "rta.interest.mortgage_status",
        labelKey: "rta.fact.mortgage_status",
        fieldKey: null,
        value: "NOT_FOUND_IN_CURRENT_SEARCH",
        originalValue: "NOT_FOUND_IN_CURRENT_SEARCH",
      }),
    ];
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    expect(
      await screen.findByText(
        en.enums.encumbranceStatus.NOT_FOUND_IN_CURRENT_SEARCH,
      ),
    ).toBeTruthy();
    await open();
    expect(
      screen.getAllByText(
        en.enums.encumbranceStatus.NOT_FOUND_IN_CURRENT_SEARCH,
      ).length,
    ).toBeGreaterThan(2);
    expect(screen.queryByText("NOT_FOUND_IN_CURRENT_SEARCH")).toBeNull();
  });
  it("offers parcel subjects for TITLE information without assigning the first choice", async () => {
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await screen.findByText("SYNTHETIC CURRENT");
    fireEvent.click(screen.getByRole("button", { name: "Add information" }));
    fireEvent.change(screen.getByLabelText("Information type"), {
      target: { value: "rta.party.holder_name_en" },
    });
    fireEvent.change(screen.getByLabelText("Fact subject"), {
      target: { value: "party-1" },
    });
    fireEvent.change(screen.getByLabelText("Information type"), {
      target: { value: "rta.title.certificate_no" },
    });
    const select = screen.getByLabelText("Fact subject") as HTMLSelectElement;
    expect(select.value).toBe("");
    expect(
      within(select).getByRole("option", { name: "Parcel 1" }),
    ).toBeTruthy();
    expect(within(select).queryByRole("option", { name: /Party/ })).toBeNull();
    fireEvent.change(screen.getByLabelText("Information value"), {
      target: { value: "SYNTHETIC TITLE" },
    });
    fireEvent.change(screen.getByLabelText("Reason for manual information"), {
      target: { value: "Synthetic type change" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save for review" }));
    await waitFor(() =>
      expect(calls.some((c) => c.init.method === "POST")).toBe(true),
    );
    expect(
      calls.find((c) => c.init.method === "POST")!.body.subjectId,
    ).toBeNull();
  });
  it("shows reviewed values without a form and preserves original/history after refetch", async () => {
    const first = renderWithIntl(<FactsScreen matterId="mat-1" />);
    await screen.findByText("SYNTHETIC CURRENT");
    expect(calls.some((c) => c.path.includes("forms"))).toBe(false);
    await open();
    expect(screen.getAllByText("SYNTHETIC ORIGINAL").length).toBeGreaterThan(0);
    expect(await screen.findByText("Synthetic correction")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Corrected value"), {
      target: { value: "SYNTHETIC CORRECTED" },
    });
    fireEvent.change(screen.getByLabelText("Reason for this decision"), {
      target: { value: "Synthetic new correction" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save correction" }));
    await screen.findAllByText("SYNTHETIC CORRECTED");
    first.unmount();
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await screen.findByText("SYNTHETIC CORRECTED");
    await open();
    expect(await screen.findByText("Synthetic correction")).toBeTruthy();
  });
  it("disables decisions when the current review read fails", async () => {
    failurePaths["/api/v1/matters/mat-1/facts/fact-1"] = 503;
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    await screen.findByRole("alert");
    expect(
      (screen.getByRole("button", { name: "Accept fact" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });
  it("filters two structural subjects deliberately", async () => {
    facts.push(
      fact({ id: "fact-2", subjectId: "party-2", value: "SYNTHETIC SECOND" }),
    );
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await screen.findByText("SYNTHETIC SECOND");
    fireEvent.change(screen.getByLabelText("Filter by subject"), {
      target: { value: "party-2" },
    });
    expect(screen.queryByText("SYNTHETIC CURRENT")).toBeNull();
  });
  it("allows transaction-only scope when the governed subject does not require a party or parcel", async () => {
    facts = [
      fact({
        factTypeId: "rta.interest.mortgage_status",
        labelKey: "rta.fact.mortgage_status",
        fieldKey: null,
        value: "NOT_FOUND_IN_CURRENT_SEARCH",
        subjectId: null,
        transactionId: null,
        scopeStatus: "unassigned",
      }),
    ];
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    fireEvent.change(screen.getByLabelText("Fact transaction"), {
      target: { value: "tx-1" },
    });
    fireEvent.change(screen.getByLabelText("Reason for this decision"), {
      target: { value: "Synthetic transaction-only association" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save association" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.endsWith("/associate"))).toBe(true),
    );
    expect(
      calls.find((c) => c.path.endsWith("/associate"))!.body,
    ).toMatchObject({ subjectId: null, transactionId: "tx-1" });
  });
  it("uses returned successor/version/token after deliberate association", async () => {
    facts = [
      fact({
        subjectId: null,
        transactionId: null,
        scopeStatus: "unassigned",
        status: "EXTRACTED_CANDIDATE",
      }),
    ];
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    expect(
      (screen.getByRole("button", { name: "Accept fact" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    fireEvent.change(screen.getByLabelText("Fact transaction"), {
      target: { value: "tx-1" },
    });
    fireEvent.change(screen.getByLabelText("Fact subject"), {
      target: { value: "party-2" },
    });
    fireEvent.change(screen.getByLabelText("Reason for this decision"), {
      target: { value: "Synthetic role association" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save association" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.endsWith("/associate"))).toBe(true),
    );
    await waitFor(() =>
      expect(
        (
          screen.getByRole("button", {
            name: "Accept fact",
          }) as HTMLButtonElement
        ).disabled,
      ).toBe(false),
    );
    fireEvent.click(screen.getByRole("button", { name: "Accept fact" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.endsWith("/accept"))).toBe(true),
    );
    const call = calls.find((c) => c.path.endsWith("/accept"))!;
    expect(call.path).toContain("fact-1-next/accept");
    expect(call.body.expectedScopeToken).toBe("returned-token");
    expect(call.body).not.toHaveProperty("subjectId");
    expect((call.init.headers as Record<string, string>)["If-Match"]).toBe(
      '"3"',
    );
  });
  it("retrieves conflict alternatives before enabling explicit resolution", async () => {
    facts = [fact({ conflictFactIds: ["peer"], status: "CONFLICTED" })];
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    expect(await screen.findByText("SYNTHETIC PEER")).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: "Accept fact" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    fireEvent.click(
      screen.getByLabelText(
        "Resolve the displayed alternatives with this decision",
      ),
    );
    fireEvent.change(screen.getByLabelText("Reason for this decision"), {
      target: { value: "Synthetic conflict choice" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Accept fact" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.endsWith("/accept"))).toBe(true),
    );
    expect(
      calls.find((c) => c.path.endsWith("/accept"))!.body.resolveFactIds,
    ).toEqual(["peer"]);
  });
  it("retains the same key for a network-refused identical intent", async () => {
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    refuse = 403;
    fireEvent.click(screen.getByRole("button", { name: "Accept fact" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Accept fact" }));
    await waitFor(() =>
      expect(calls.filter((c) => c.path.endsWith("/accept")).length).toBe(2),
    );
    const attempts = calls.filter((c) => c.path.endsWith("/accept"));
    expect(
      (attempts[0]!.init.headers as Record<string, string>)["Idempotency-Key"],
    ).toBe(
      (attempts[1]!.init.headers as Record<string, string>)["Idempotency-Key"],
    );
  });
  it("renews review on 412 without retrying the mutation", async () => {
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    facts = [fact({ version: 9, scopeToken: "fresh-server-token" })];
    refuse = 412;
    fireEvent.click(screen.getByRole("button", { name: "Accept fact" }));
    await screen.findByText(
      "The record changed. Review the refreshed value and alternatives before deciding again.",
    );
    expect(calls.filter((c) => c.path.endsWith("/accept")).length).toBe(1);
    expect(
      calls.filter((c) => c.path.endsWith("/facts/fact-1")).length,
    ).toBeGreaterThan(1);
    await waitFor(() =>
      expect(
        (
          screen.getByRole("button", {
            name: "Accept fact",
          }) as HTMLButtonElement
        ).disabled,
      ).toBe(false),
    );
    fireEvent.click(screen.getByRole("button", { name: "Accept fact" }));
    await waitFor(() =>
      expect(calls.filter((c) => c.path.endsWith("/accept"))).toHaveLength(2),
    );
    const renewed = calls.filter((c) => c.path.endsWith("/accept"))[1]!;
    expect((renewed.init.headers as Record<string, string>)["If-Match"]).toBe(
      '"9"',
    );
    expect(renewed.body.expectedScopeToken).toBe("fresh-server-token");
  });
  it("exposes deliberate next-page loading", async () => {
    more = true;
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await screen.findByText("SYNTHETIC CURRENT");
    fireEvent.click(screen.getByRole("button", { name: "Load more facts" }));
    await screen.findByText("SYNTHETIC NEXT PAGE");
    expect(calls.some((c) => c.path.includes("cursor=signed-page-2"))).toBe(
      true,
    );
  });
  it("labels a broken fact cursor even when all reference menus finish loading", async () => {
    brokenCursor = true;
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await screen.findByText("SYNTHETIC CURRENT");
    await waitFor(() =>
      expect(calls.some((c) => c.path.endsWith("/fact-types"))).toBe(true),
    );
    expect(screen.getByText(en.factRegister.partialFacts)).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Load more facts" }),
    ).toBeNull();
  });
  it("loads subsequent signed history pages without replacing the visible decision", async () => {
    historyMore = true;
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    fireEvent.click(
      await screen.findByRole("button", { name: "Load more history" }),
    );
    await screen.findByText("Synthetic older decision");
    expect(screen.getByText("Synthetic correction")).toBeTruthy();
    expect(calls.some((c) => c.path.includes("cursor=signed-history-2"))).toBe(
      true,
    );
  });

  it("saves manual information for review without promoting it", async () => {
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await screen.findByText("SYNTHETIC CURRENT");
    fireEvent.click(screen.getByRole("button", { name: "Add information" }));
    fireEvent.change(screen.getByLabelText("Information type"), {
      target: { value: "rta.party.holder_name_en" },
    });
    fireEvent.change(screen.getByLabelText("Information value"), {
      target: { value: "SYNTHETIC MANUAL" },
    });
    fireEvent.change(screen.getByLabelText("Reason for manual information"), {
      target: { value: "Synthetic missing information" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save for review" }));
    await screen.findAllByText("SYNTHETIC MANUAL");
    const write = calls.find((c) => c.init.method === "POST")!;
    expect(write.body).toMatchObject({
      value: "SYNTHETIC MANUAL",
      reason: "Synthetic missing information",
    });
    expect(write.body).not.toHaveProperty("evidence");
    expect(calls.some((c) => c.path.endsWith("/accept"))).toBe(false);
    expect(await screen.findByText(/Lawyer-entered information/)).toBeTruthy();
  });
  it("reuses the manual intent after an ambiguous save and reload with matching re-entry", async () => {
    const first = renderWithIntl(<FactsScreen matterId="mat-1" />);
    async function enter() {
      await screen.findByText("SYNTHETIC CURRENT");
      fireEvent.click(screen.getByRole("button", { name: "Add information" }));
      fireEvent.change(screen.getByLabelText("Information type"), {
        target: { value: "rta.party.holder_name_en" },
      });
      fireEvent.change(screen.getByLabelText("Information value"), {
        target: { value: "SYNTHETIC PRIVATE RE-ENTRY" },
      });
      fireEvent.change(screen.getByLabelText("Reason for manual information"), {
        target: { value: "SYNTHETIC PRIVATE REASON" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Save for review" }));
    }
    failurePaths["/api/v1/matters/mat-1/facts"] = 503;
    await enter();
    await screen.findByRole("alert");
    const write = calls.find((c) => c.init.method === "POST")!;
    expect(JSON.stringify(Object.values(sessionStorage))).not.toContain(
      "SYNTHETIC PRIVATE",
    );
    first.unmount();
    delete failurePaths["/api/v1/matters/mat-1/facts"];
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await enter();
    await screen.findAllByText("SYNTHETIC PRIVATE RE-ENTRY");
    const retry = calls.filter((c) => c.init.method === "POST").at(-1)!;
    expect(new Headers(retry.init.headers).get("Idempotency-Key")).toBe(
      new Headers(write.init.headers).get("Idempotency-Key"),
    );
    expect(sessionStorage.length).toBe(0);
  });
  it("displays page attribution honestly when OCR text is absent", async () => {
    facts = [
      fact({
        evidence: [
          {
            ...fact().evidence[0]!,
            supportingText: null,
            pageText: null,
            precision: "page",
          },
        ],
      }),
    ];
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    expect(
      await screen.findByText(
        "Page-level attribution; no exact text match is available.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Stored OCR text is unavailable.")).toBeTruthy();
    expect(
      screen.queryByText(
        "Text match in stored OCR; no exact location is claimed.",
      ),
    ).toBeNull();
  });
  it("refuses to act on unavailable alternatives", async () => {
    facts = [fact({ conflictFactIds: ["peer"] })];
    failurePaths["/api/v1/matters/mat-1/facts/peer"] = 404;
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    await screen.findByRole("alert");
    expect(
      (screen.getByRole("button", { name: "Accept fact" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });
  it("keeps rejected information distinct from a missing fact", async () => {
    facts = [fact({ status: "REJECTED" })];
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    expect(screen.getAllByText("Rejected").length).toBeGreaterThan(0);
    expect(
      (screen.getByRole("button", { name: "Accept fact" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(screen.getAllByText("SYNTHETIC CURRENT").length).toBeGreaterThan(0);
  });
  it("displays unavailable API state without a false empty register", async () => {
    failurePaths["/api/v1/matters/mat-1/facts?limit=50"] = 503;
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(
      screen.queryByText(
        "No facts match these choices. Add information or review documents.",
      ),
    ).toBeNull();
  });
  it("withholds foreign facts even from an invalid response", async () => {
    facts = [fact({ matterId: "foreign" })];
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await screen.findByRole("alert");
    expect(screen.queryByText("SYNTHETIC CURRENT")).toBeNull();
  });
  it("reports original source access refusal", async () => {
    failurePaths["/api/v1/source-files/source/content"] = 403;
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Load original file" }));
    await screen.findByRole("alert");
    expect(calls.some((c) => c.path.endsWith("/source/content"))).toBe(true);
  });
  it("requires current evidence while leaving rejection actionable", async () => {
    facts = [fact({ evidenceStale: true })];
    renderWithIntl(<FactsScreen matterId="mat-1" />);
    await open();
    expect(
      (screen.getByRole("button", { name: "Accept fact" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    fireEvent.change(screen.getByLabelText("Reason for this decision"), {
      target: { value: "Synthetic stale-source rejection" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject fact" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.endsWith("/reject"))).toBe(true),
    );
    expect(
      calls.find((c) => c.path.endsWith("/reject"))!.body,
    ).not.toHaveProperty("subjectId");
  });
  it("does not display late responses from a previous matter", async () => {
    const view = renderWithIntl(<FactsScreen matterId="mat-OLD" />);
    await waitFor(() => expect(pending).toBeTruthy());
    view.rerender(
      <NextIntlClientProvider locale="en" messages={en} timeZone="Asia/Colombo">
        <FactsScreen matterId="mat-1" />
      </NextIntlClientProvider>,
    );
    await screen.findByText("SYNTHETIC CURRENT");
    pending!(
      response({
        items: [fact({ value: "LATE OLD MATTER", matterId: "mat-OLD" })],
        page: pageInfo,
      }),
    );
    await waitFor(() =>
      expect(screen.queryByText("LATE OLD MATTER")).toBeNull(),
    );
  });
});
