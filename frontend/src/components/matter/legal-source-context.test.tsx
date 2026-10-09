// @vitest-environment happy-dom
import { useCallback, useState } from "react";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import en from "@/lib/i18n/messages/en.json";
import si from "@/lib/i18n/messages/si.json";
import type {
  ApiLegalAuthority,
  ApiLegalContext,
  ApiResearchSelection,
} from "@/lib/api/agent";
import type { ApiMatterTransaction } from "@/types/rta";

const api = vi.hoisted(() => ({
  transactions: vi.fn(),
  token: async () => "synthetic-token",
}));
vi.mock("@/lib/api/facts", () => ({ listTransactions: api.transactions }));
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => api.token,
}));

import {
  LegalAuthorityPanel,
  LegalResultContext,
  LegalTransactionSelector,
  type LegalSourceSelection,
} from "./legal-source-context";

// All records below are synthetic; dates are fixed historical result pins.
function authority(
  overrides: Partial<ApiLegalAuthority> = {},
): ApiLegalAuthority {
  return {
    sourceId: "synthetic-statute",
    title: "Synthetic source title",
    reference: "Synthetic source reference",
    kind: "statute",
    sourceUrl: "https://example.com/synthetic-source",
    sourceSha256: "a".repeat(64),
    publicationDate: "2020-01-02",
    effectiveFrom: "2020-02-03",
    effectiveTo: null,
    commencementKnown: true,
    commencementSourceId: null,
    commencementPage: null,
    relationships: [],
    releaseVersion: "synthetic-release-1",
    reviewState: "approved",
    currencyStatus: "current",
    ...overrides,
  };
}
function context(overrides: Partial<ApiLegalContext> = {}): ApiLegalContext {
  return {
    kind: "result",
    transactionId: "synthetic-transaction",
    associationVersion: 7,
    dateContext: {
      currentDate: "2026-09-01",
      transactionId: "synthetic-transaction",
      associationVersion: 7,
      transactionDate: "2024-03-04",
      factId: "synthetic-date-fact",
      factVersion: 3,
      reason: "reviewed-date",
    },
    authorities: [],
    coverageGaps: [],
    sourceReleaseVersion: "synthetic-release-1",
    unavailableReason: null,
    visibility: "available",
    ...overrides,
  };
}
function selection(
  source: ApiLegalAuthority,
  overrides: Partial<LegalSourceSelection> = {},
): LegalSourceSelection {
  return {
    sourceId: source.sourceId,
    sourceType: source.kind,
    label: source.reference,
    locator: null,
    verificationStatus: "unverified",
    authorityMetadata: source,
    metadataLead: true,
    ...overrides,
  };
}
function transaction(
  id: string,
  ordinal: number,
  version: number,
): ApiMatterTransaction {
  return {
    id,
    ordinal,
    version,
    userId: "synthetic-user",
    matterId: "synthetic-matter",
    parcelSubjectIds: [],
    partyRoles: [],
  };
}
function page(
  items: ApiMatterTransaction[],
  hasMore = false,
  nextCursor: string | null = null,
) {
  return { items, page: { limit: 100, hasMore, nextCursor } };
}

beforeEach(() => {
  api.transactions.mockReset();
  api.transactions.mockResolvedValue(page([]));
});

describe("legal result context", () => {
  it.each(["en", "si"] as const)(
    "explains distinct coverage gaps in %s and safely deduplicates unknown reasons",
    (locale) => {
      const messages = (locale === "en" ? en : si).matterAssistant;
      renderWithIntl(
        <LegalResultContext
          matterId="synthetic-matter"
          onSelect={vi.fn()}
          context={context({
            coverageGaps: [
              "requested-authority-missing",
              "authority-metadata-unsupported",
              "source-passages-withheld",
              "source-release-unavailable",
              "quotation-boundary-unavailable",
              "requested-authority-missing",
              "synthetic-internal-reason",
              "another-unknown-reason",
            ],
          })}
        />,
        locale,
      );
      const warnings = screen.getAllByRole("listitem");
      expect(warnings).toHaveLength(6);
      for (const message of Object.values(messages.legalCoverageReasons)) {
        expect(screen.getAllByText(message)).toHaveLength(1);
      }
      expect(
        screen.getAllByText(messages.legalCoverageUnavailable),
      ).toHaveLength(1);
      expect(
        screen.queryByText(/synthetic-internal-reason|another-unknown-reason/),
      ).toBeNull();
      expect(screen.queryByRole("button")).toBeNull();
    },
  );

  it("retains the recorded date and version pins when opening an unverified metadata lead", () => {
    const source = authority();
    const recorded = context({
      authorities: [source],
      visibility: "current-policy-unavailable",
    });
    const onSelect = vi.fn<(value: LegalSourceSelection) => void>();
    renderWithIntl(
      <LegalResultContext
        context={recorded}
        matterId="synthetic-matter"
        onSelect={onSelect}
      />,
    );
    expect(
      screen.getByText("Current date when requested: 2026-09-01"),
    ).toBeTruthy();
    expect(
      screen.getByText("Reviewed transaction date: 2024-03-04"),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Recorded transaction: synthetic-transaction \u00b7 revision 7",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Recorded date fact: synthetic-date-fact \u00b7 version 3",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText("Source metadata release: synthetic-release-1"),
    ).toBeTruthy();
    expect(
      screen.getByText(en.matterAssistant.legalHistoryUnavailable),
    ).toBeTruthy();
    expect(
      screen.queryByRole("link", { name: en.matterAssistant.legalReviewFacts }),
    ).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: source.reference }));
    expect(onSelect).toHaveBeenCalledExactlyOnceWith({
      sourceId: source.sourceId,
      sourceType: source.kind,
      label: source.reference,
      locator: null,
      verificationStatus: "unverified",
      authorityMetadata: source,
      corpusVersion: source.releaseVersion,
      legalContext: recorded,
      metadataLead: true,
    });
    expect(onSelect.mock.calls[0]![0]).not.toHaveProperty("passage");
  });

  it.each(["date-missing", "date-conflict", "transaction-required"] as const)(
    "directs %s back to reviewed facts without inventing dates or versions",
    (reason) => {
      const recorded = context();
      recorded.dateContext = {
        ...recorded.dateContext!,
        reason,
        transactionDate: null,
        associationVersion: null,
        factVersion: null,
      };
      renderWithIntl(
        <LegalResultContext
          context={recorded}
          matterId="synthetic-matter"
          onSelect={vi.fn()}
        />,
      );
      expect(
        screen.getByText("Reviewed transaction date: Unknown"),
      ).toBeTruthy();
      expect(
        screen.getByText(
          "Recorded transaction: synthetic-transaction \u00b7 revision Unknown",
        ),
      ).toBeTruthy();
      expect(
        screen.getByText(
          "Recorded date fact: synthetic-date-fact \u00b7 version Unknown",
        ),
      ).toBeTruthy();
      expect(
        screen
          .getByRole("link", { name: en.matterAssistant.legalReviewFacts })
          .getAttribute("href"),
      ).toBe("/matters/synthetic-matter/facts");
      expect(
        screen.queryByText("Reviewed transaction date: 2024-03-04"),
      ).toBeNull();
    },
  );

  it("does not fabricate missing date context, release, or scope identifiers", () => {
    const source = authority({ reference: "" });
    const onSelect = vi.fn<(value: LegalSourceSelection) => void>();
    renderWithIntl(
      <LegalResultContext
        context={context({
          dateContext: null,
          sourceReleaseVersion: null,
          authorities: [source],
        })}
        matterId="synthetic-matter"
        onSelect={onSelect}
      />,
    );
    expect(
      screen.queryByText(
        /Current date when requested:|Recorded transaction:|Recorded date fact:|Source metadata release:/,
      ),
    ).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: source.title }));
    expect(onSelect.mock.calls[0]![0].label).toBe(source.title);
  });

  it("shows incomplete date context without manufacturing transaction or fact pins", () => {
    const recorded = context();
    recorded.dateContext = {
      ...recorded.dateContext!,
      transactionId: null,
      factId: null,
      reason: "transaction-required",
    };
    renderWithIntl(
      <LegalResultContext
        context={recorded}
        matterId="synthetic-matter"
        onSelect={vi.fn()}
      />,
    );
    expect(
      screen.queryByText(/Recorded transaction:|Recorded date fact:/),
    ).toBeNull();
    expect(
      screen.getByRole("link", { name: en.matterAssistant.legalReviewFacts }),
    ).toBeTruthy();
  });
});

describe("legal authority metadata", () => {
  it("shows provenance and known commencement without presenting metadata as a passage", () => {
    const source = authority({
      effectiveTo: "2025-12-31",
      commencementSourceId: "synthetic-gazette",
      commencementPage: 8,
    });
    renderWithIntl(
      <LegalAuthorityPanel
        selection={selection(source)}
        matterId="synthetic-matter"
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText(en.matterAssistant.legalMetadataLead)).toBeTruthy();
    expect(
      screen.getByText("Source review: Source release reviewed"),
    ).toBeTruthy();
    expect(screen.getByText("Publication date: 2020-01-02")).toBeTruthy();
    expect(
      screen.getByText("Recorded effective date: 2020-02-03"),
    ).toBeTruthy();
    expect(screen.getByText("Recorded end date: 2025-12-31")).toBeTruthy();
    expect(
      screen.getByText("Commencement source: synthetic-gazette \u00b7 page 8"),
    ).toBeTruthy();
    expect(screen.getByText(source.sourceSha256)).toBeTruthy();
    const official = screen.getByRole("link", {
      name: en.matterAssistant.legalOfficialSource,
    });
    expect(official.getAttribute("href")).toBe(source.sourceUrl);
    expect(official.getAttribute("target")).toBe("_blank");
    expect(official.getAttribute("rel")).toBe("noopener noreferrer");
    expect(
      screen.queryByText(en.matterAssistant.legalCommencementUnknown),
    ).toBeNull();
  });

  it("keeps unknown commencement and unknown review status explicit despite a publication date", () => {
    const source = authority({
      commencementKnown: false,
      reviewState: "synthetic-new-review-state",
      commencementSourceId: "synthetic-gazette",
      commencementPage: null,
    });
    renderWithIntl(
      <LegalAuthorityPanel
        selection={selection(source, { metadataLead: false })}
        matterId="synthetic-matter"
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("Publication date: 2020-01-02")).toBeTruthy();
    expect(screen.getByText("Recorded effective date: Unknown")).toBeTruthy();
    expect(screen.getByText("Recorded end date: Unknown")).toBeTruthy();
    expect(screen.getByText("Source review: Unknown")).toBeTruthy();
    expect(
      screen.getByText(
        "Commencement source: synthetic-gazette \u00b7 page Unknown",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText(en.matterAssistant.legalCommencementUnknown),
    ).toBeTruthy();
    expect(
      screen.queryByText("Recorded effective date: 2020-02-03"),
    ).toBeNull();
    expect(screen.queryByText(en.matterAssistant.legalMetadataLead)).toBeNull();
  });

  it("does not invent missing publication or effective dates even when commencement is recorded", () => {
    renderWithIntl(
      <LegalAuthorityPanel
        selection={selection(
          authority({ publicationDate: null, effectiveFrom: null }),
        )}
        matterId="synthetic-matter"
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("Publication date: Unknown")).toBeTruthy();
    expect(screen.getByText("Recorded effective date: Unknown")).toBeTruthy();
    expect(
      screen.queryByText(en.matterAssistant.legalCommencementUnknown),
    ).toBeNull();
  });

  it.each([
    "http://example.com/source",
    "javascript:alert(1)",
    "https://user@example.com/source",
    "https://:password@example.com/source",
    "not a URL",
  ])("withholds an unsafe official link: %s", (sourceUrl) => {
    renderWithIntl(
      <LegalAuthorityPanel
        selection={selection(authority({ sourceUrl }))}
        matterId="synthetic-matter"
        onSelect={vi.fn()}
      />,
    );
    expect(
      screen.queryByRole("link", {
        name: en.matterAssistant.legalOfficialSource,
      }),
    ).toBeNull();
    expect(screen.getByText(en.matterAssistant.legalMetadataLead)).toBeTruthy();
  });

  it("preserves relationship direction, review provenance, and the historical target when inspecting a lead", () => {
    const target = authority({
      sourceId: "synthetic-target",
      reference: "Synthetic target",
    });
    const source = authority({
      relationships: [
        {
          relation: "amends",
          targetSourceId: target.sourceId,
          targetReference: null,
          supportingPage: 4,
          reviewState: "reviewed",
        },
        {
          relation: "supersedes",
          targetSourceId: target.sourceId,
          targetReference: "Synthetic historical target label",
          supportingPage: 5,
          reviewState: "reviewed",
        },
        {
          relation: "made-under",
          targetSourceId: "synthetic-unavailable",
          targetReference: "Synthetic missing reference",
          supportingPage: null,
          reviewState: "unreviewed",
        },
        {
          relation: "commences",
          targetSourceId: "synthetic-unavailable-id",
          targetReference: null,
          supportingPage: null,
          reviewState: "unreviewed",
        },
      ],
    });
    const recorded = context({ authorities: [target] });
    const onSelect = vi.fn<(value: LegalSourceSelection) => void>();
    renderWithIntl(
      <LegalAuthorityPanel
        selection={selection(source, { legalContext: recorded })}
        matterId="synthetic-matter"
        onSelect={onSelect}
      />,
    );
    const relationships = screen.getByRole("list");
    const rows = within(relationships).getAllByRole("listitem");
    expect(rows).toHaveLength(4);
    expect(
      within(rows[0]!).getByText(en.matterAssistant.legalRelations.amends),
    ).toBeTruthy();
    expect(
      within(rows[0]!).getByText(
        "Relationship source page: 4 \u00b7 Relationship reviewed",
      ),
    ).toBeTruthy();
    fireEvent.click(
      within(rows[0]!).getByRole("button", { name: target.reference }),
    );
    expect(onSelect.mock.calls[0]![0]).toMatchObject({
      sourceId: target.sourceId,
      authorityMetadata: target,
      legalContext: recorded,
      metadataLead: true,
      verificationStatus: "unverified",
    });
    expect(onSelect.mock.calls[0]![0]).not.toHaveProperty("passage");
    fireEvent.click(
      within(rows[1]!).getByRole("button", {
        name: "Synthetic historical target label",
      }),
    );
    expect(onSelect.mock.calls[1]![0].sourceId).toBe(target.sourceId);
    expect(
      within(rows[2]!).getByText("Synthetic missing reference"),
    ).toBeTruthy();
    expect(within(rows[3]!).getByText("synthetic-unavailable-id")).toBeTruthy();
    expect(
      within(rows[2]!).getByText(
        "Relationship source page: Unknown \u00b7 Relationship not reviewed",
      ),
    ).toBeTruthy();
    expect(within(rows[2]!).queryByRole("button")).toBeNull();
    expect(within(rows[3]!).queryByRole("button")).toBeNull();
    expect(
      screen.getByRole("region", { name: en.matterAssistant.legalContext }),
    ).toBeTruthy();
  });

  it("keeps relationships without available context as non-actionable metadata", () => {
    const source = authority({
      relationships: [
        {
          relation: "amends",
          targetSourceId: "synthetic-target",
          targetReference: null,
          supportingPage: null,
          reviewState: "unreviewed",
        },
      ],
    });
    renderWithIntl(
      <LegalAuthorityPanel
        selection={selection(source)}
        matterId="synthetic-matter"
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("synthetic-target")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("does not render authority claims for an ordinary citation without metadata", () => {
    const { container } = renderWithIntl(
      <LegalAuthorityPanel
        selection={{
          sourceId: "synthetic-document",
          sourceType: "document",
          label: "Synthetic original",
          locator: null,
          verificationStatus: "unverified",
        }}
        matterId="synthetic-matter"
        onSelect={vi.fn()}
      />,
    );
    expect(container.textContent).toBe("");
  });
});

describe("explicit legal transaction selection", () => {
  it("loads every page, requires an explicit id/version, and clears the choice on refresh", async () => {
    const first = transaction("synthetic-first", 1, 2);
    const second = transaction("synthetic-second", 2, 9);
    api.transactions
      .mockResolvedValueOnce(page([first], true, "synthetic-next"))
      .mockResolvedValueOnce(page([second]));
    const onChange = vi.fn();
    function ControlledSelection() {
      const [value, setValue] = useState<ApiResearchSelection | null>(null);
      const change = useCallback((next: ApiResearchSelection | null) => {
        setValue(next);
        onChange(next);
      }, []);
      return (
        <LegalTransactionSelector
          matterId="synthetic-matter"
          value={value}
          onChange={change}
          disabled={false}
        />
      );
    }
    renderWithIntl(<ControlledSelection />);
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    await waitFor(() => expect(select.disabled).toBe(false));
    expect(api.transactions).toHaveBeenNthCalledWith(
      1,
      api.token,
      "synthetic-matter",
      { limit: 100, cursor: undefined },
    );
    expect(api.transactions).toHaveBeenNthCalledWith(
      2,
      api.token,
      "synthetic-matter",
      { limit: 100, cursor: "synthetic-next" },
    );
    expect(within(select).getAllByRole("option")).toHaveLength(3);
    expect(select.value).toBe("");
    expect(onChange.mock.calls).toEqual([[null]]);
    fireEvent.change(select, { target: { value: "synthetic-second:9" } });
    expect(onChange).toHaveBeenLastCalledWith({
      transactionId: "synthetic-second",
      associationVersion: 9,
    });
    expect(select.value).toBe("synthetic-second:9");
    fireEvent.change(select, { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith(null);
    expect(select.value).toBe("");
    fireEvent.change(select, { target: { value: "synthetic-second:9" } });
    // The parent owns the controlled choice; refresh must explicitly invalidate it.
    onChange.mockClear();
    fireEvent.click(
      screen.getByRole("button", {
        name: en.matterAssistant.refreshLegalTransactions,
      }),
    );
    expect(onChange).toHaveBeenCalledExactlyOnceWith(null);
    expect(select.value).toBe("");
    await waitFor(() => expect(api.transactions).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(select.disabled).toBe(false));
  });

  it.each(["missing", "repeated", "budget"] as const)(
    "discards partial transactions when pagination is %s",
    async (failure) => {
      const row = transaction("synthetic-incomplete", 1, 3);
      if (failure === "missing")
        api.transactions.mockResolvedValue(page([row], true, null));
      if (failure === "repeated")
        api.transactions.mockResolvedValue(
          page([row], true, "synthetic-repeat"),
        );
      if (failure === "budget")
        api.transactions.mockImplementation(async () =>
          page(
            [row],
            true,
            `synthetic-cursor-${api.transactions.mock.calls.length}`,
          ),
        );
      const onChange = vi.fn();
      renderWithIntl(
        <LegalTransactionSelector
          matterId="synthetic-matter"
          value={{ transactionId: row.id, associationVersion: row.version }}
          onChange={onChange}
          disabled={false}
        />,
      );
      expect(await screen.findByRole("alert")).toHaveProperty(
        "textContent",
        en.matterAssistant.legalTransactionsUnavailable,
      );
      expect((screen.getByRole("combobox") as HTMLSelectElement).disabled).toBe(
        true,
      );
      expect(screen.getAllByRole("option")).toHaveLength(1);
      expect(api.transactions).toHaveBeenCalledTimes(
        failure === "missing" ? 1 : failure === "repeated" ? 2 : 100,
      );
      expect(onChange).toHaveBeenCalledExactlyOnceWith(null);
      expect(
        (
          screen.getByRole("button", {
            name: en.matterAssistant.refreshLegalTransactions,
          }) as HTMLButtonElement
        ).disabled,
      ).toBe(false);
    },
  );

  it("keeps the transaction and refresh controls disabled while the parent is busy", async () => {
    api.transactions.mockResolvedValue(
      page([transaction("synthetic-choice", 1, 4)]),
    );
    const onChange = vi.fn();
    renderWithIntl(
      <LegalTransactionSelector
        matterId="synthetic-matter"
        value={{ transactionId: "synthetic-choice", associationVersion: 4 }}
        onChange={onChange}
        disabled
      />,
    );
    await screen.findByRole("option", {
      name: "Transaction 1 \u00b7 revision 4",
    });
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.disabled).toBe(true);
    expect(select.value).toBe("synthetic-choice:4");
    expect(
      (
        screen.getByRole("button", {
          name: en.matterAssistant.refreshLegalTransactions,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(api.transactions).toHaveBeenCalledTimes(1);
  });
});
