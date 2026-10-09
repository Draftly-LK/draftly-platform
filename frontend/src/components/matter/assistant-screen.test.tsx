// @vitest-environment happy-dom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";

// Every call answers with an empty, synthetic matter so the screen settles without a backend.
const turns = vi.hoisted(() => ({
  send: vi.fn(),
  retry: vi.fn(),
  read: vi.fn(),
  stream: vi.fn(),
  latest: vi.fn(),
  receipt: vi.fn(),
  messages: vi.fn(),
  action: vi.fn(),
  confirm: vi.fn(),
  reject: vi.fn(),
  fresh: vi.fn(),
  source: vi.fn(),
  transactions: vi.fn(),
  token: async () => null,
}));
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => turns.token,
}));
vi.mock("@/lib/api/agent", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    sendAgentMessage: turns.send,
    retryAgentJob: turns.retry,
    getAgentJob: turns.read,
    streamAgentJobEvents: turns.stream,
    getLatestAgentJob: turns.latest,
    getAgentSendReceipt: turns.receipt,
    getAgentSession: async () => ({ activeConversationId: "conv-1" }),
    getAgentAction: turns.action,
    confirmAgentAction: turns.confirm,
    rejectAgentAction: turns.reject,
    startAgentConversation: turns.fresh,
    listAgentMessages: turns.messages,
  };
});
vi.mock("@/lib/api/auth", () => ({
  getMe: async () => ({ id: "synthetic-user" }),
}));
vi.mock("@/lib/api/matters", () => ({
  getMatter: async () => ({
    reference: "RTA-SYN-0001",
    state: "EVIDENCE_COLLECTION",
  }),
  getChecklist: async () => null,
}));
vi.mock("@/lib/api/documents", () => ({
  getCompleteDocumentInbox: async () => null,
  getSourceFile: turns.source,
}));
vi.mock("@/lib/api/facts", () => ({
  listMatterFacts: async () => ({ items: [] }),
  listTransactions: turns.transactions,
}));
vi.mock("@/lib/api/checks", () => ({
  listCompleteIssues: async () => ({ items: [] }),
}));
vi.mock("@/lib/api/drafts", () => ({ listForms: async () => ({ items: [] }) }));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("./source-file-preview", () => ({
  SourceFilePreview: ({
    sourceFileId,
    pageStart,
  }: {
    sourceFileId: string;
    pageStart: number;
  }) => (
    <div data-testid="original-preview">
      {sourceFileId}:{pageStart}
    </div>
  ),
}));

import { ApiError } from "@/lib/api/client";
import messages from "@/lib/i18n/messages/en.json";
import sinhala from "@/lib/i18n/messages/si.json";
import { MatterAssistantScreen } from "./assistant-screen";
import { MatterConversation } from "./matter-conversation";

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  turns.latest.mockReset().mockResolvedValue(null);
  turns.receipt.mockReset().mockResolvedValue(null);
  turns.messages.mockReset().mockResolvedValue({
    items: [],
    page: { hasMore: false, nextCursor: null },
  });
  turns.action.mockReset();
  turns.confirm.mockReset();
  turns.reject.mockReset();
  turns.fresh.mockReset();
  turns.source.mockReset();
  turns.transactions.mockReset().mockResolvedValue({
    items: [],
    page: { limit: 100, hasMore: false, nextCursor: null },
  });
  turns.send.mockReset();
  turns.retry.mockReset();
  turns.read.mockReset();
  turns.stream.mockReset().mockResolvedValue(false);
});

describe("MatterAssistantScreen", () => {
  it("reports unavailable transaction selection and refreshes without sending a turn", async () => {
    turns.transactions.mockRejectedValueOnce(
      new Error("Synthetic list unavailable"),
    );
    renderWithIntl(<MatterAssistantScreen matterId="m1" />);
    const select = screen.getByLabelText(
      messages.matterAssistant.legalTransaction,
    );
    expect(
      await screen.findByText(
        messages.matterAssistant.legalTransactionsUnavailable,
      ),
    ).toBeTruthy();
    expect((select as HTMLSelectElement).disabled).toBe(true);
    turns.transactions.mockResolvedValue({
      items: [
        {
          id: "tx-synthetic",
          userId: "synthetic-user",
          matterId: "m1",
          ordinal: 1,
          version: 3,
          partyRoles: [],
          parcelSubjectIds: [],
        },
      ],
      page: { limit: 100, hasMore: false, nextCursor: null },
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: messages.matterAssistant.refreshLegalTransactions,
      }),
    );
    await within(select).findByRole("option", {
      name: "Transaction 1 \u00b7 revision 3",
    });
    await waitFor(() =>
      expect((select as HTMLSelectElement).disabled).toBe(false),
    );
    expect(
      screen.queryByText(messages.matterAssistant.legalTransactionsUnavailable),
    ).toBeNull();
    expect((select as HTMLSelectElement).value).toBe("");
    expect(turns.send).not.toHaveBeenCalled();
  });

  it("keeps polling after an SSE snapshot reports a queued job", async () => {
    const queued = {
      jobId: "job-queued",
      state: "queued",
      toolCallCount: 0,
      failureClass: null,
    };
    turns.send.mockResolvedValue(queued);
    turns.stream.mockResolvedValue(true);
    turns.read.mockResolvedValueOnce(queued).mockResolvedValue({
      ...queued,
      state: "failed",
      failureClass: "model_unavailable",
    });
    renderWithIntl(<MatterAssistantScreen matterId="m1" />);
    await screen.findByRole("button", { name: /New conversation/ });
    await waitFor(() => expect(turns.latest).toHaveBeenCalled());
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(
      await screen.findByRole("alert", {}, { timeout: 3000 }),
    ).toBeTruthy();
  });
  it("retries a failed turn without posting the saved message again", async () => {
    const failed = {
      jobId: "job-failed",
      state: "failed",
      toolCallCount: 0,
      failureClass: "model_unavailable",
    };
    const succeeded = {
      jobId: "job-retry",
      state: "succeeded",
      toolCallCount: 0,
      failureClass: null,
    };
    turns.send.mockResolvedValue(failed);
    turns.retry.mockResolvedValue(succeeded);
    turns.read.mockImplementation(async (_token, id) =>
      id === failed.jobId ? failed : succeeded,
    );
    renderWithIntl(<MatterAssistantScreen matterId="m1" />);
    await screen.findByRole("button", { name: /New conversation/ });
    await waitFor(() => expect(turns.latest).toHaveBeenCalled());
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(turns.retry).toHaveBeenCalledWith(
        expect.any(Function),
        "m1",
        "job-failed",
        expect.any(String),
      ),
    );
    expect(turns.send).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });
  it("keeps its tools in the body, and offers the context as Research's icon row on narrow screens", async () => {
    renderWithIntl(<MatterAssistantScreen matterId="m1" />);
    expect(
      await screen.findByRole("button", { name: /New conversation/ }),
    ).toBeTruthy();
    expect(screen.queryByRole("banner")).toBeNull();
    expect(screen.queryByRole("button", { name: "Matter context" })).toBeNull();
    // One open button in the wide panel's header, one in the narrow row.
    expect(
      screen.getAllByRole("button", { name: /matter context/i }).length,
    ).toBeGreaterThan(0);
  });

  it("starts folded to an icon rail, opens and folds again, and remembers the choice", async () => {
    renderWithIntl(<MatterAssistantScreen matterId="m1" />);
    const panel = screen.getByRole("complementary", { name: "Matter context" });
    expect(panel.getAttribute("data-collapsed")).toBe("true");
    // The folded column and the narrow-screen row (hidden by CSS) both link each section.
    for (const link of screen.getAllByRole("link", { name: /^Documents:/ }))
      expect(link.getAttribute("href")).toBe("/matters/m1/documents");
    fireEvent.click(
      within(panel).getByRole("button", { name: "Show matter context" }),
    );
    expect(panel.getAttribute("data-collapsed")).toBeNull();
    expect(window.localStorage.getItem("draftly-assistant-context")).toBe(
      "open",
    );
    fireEvent.click(
      within(panel).getByRole("button", { name: "Hide matter context" }),
    );
    expect(panel.getAttribute("data-collapsed")).toBe("true");
    expect(window.localStorage.getItem("draftly-assistant-context")).toBe(
      "collapsed",
    );
  });
});

describe("persistent shared conversation", () => {
  const succeeded = {
    jobId: "saved-attempt",
    state: "succeeded",
    toolCallCount: 0,
    failureClass: null,
  };
  const message = {
    id: "saved-message",
    sequence: 1,
    role: "assistant",
    content: "Synthetic saved answer",
    createdAt: "2026-10-09T00:00:00Z",
    jobId: "saved-attempt",
    pendingActionId: null,
    conversationId: "conv-1",
    citations: [],
  };

  it("resumes a running accepted job after reload without sending again", async () => {
    turns.latest.mockResolvedValue({ ...succeeded, state: "running" });
    turns.read.mockResolvedValue(succeeded);
    turns.messages.mockResolvedValue({
      items: [message],
      page: { hasMore: false },
    });
    renderWithIntl(<MatterConversation matterId="reload-synthetic" embedded />);
    await screen.findByText("Synthetic saved answer");
    await waitFor(() => expect(turns.read).toHaveBeenCalled());
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: /New conversation/ })
          .hasAttribute("disabled"),
      ).toBe(false),
    );
    expect(turns.send).not.toHaveBeenCalled();
    expect(
      screen
        .getByRole("link", { name: "Open full conversation" })
        .getAttribute("href"),
    ).toBe("/matters/reload-synthetic/assistant");
    expect(screen.queryByRole("main")).toBeNull();
  });

  it("keeps the logical send key across an ambiguous response and remount, without storing content", async () => {
    turns.send
      .mockRejectedValueOnce(new Error("transport lost response"))
      .mockResolvedValue(succeeded);
    turns.read.mockResolvedValue(succeeded);
    const first = renderWithIntl(
      <MatterConversation matterId="lost-synthetic" embedded />,
    );
    await waitFor(() => expect(turns.latest).toHaveBeenCalled());
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "synthetic confidential wording" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("alert");
    const key = turns.send.mock.calls[0]?.[3];
    expect(JSON.stringify(sessionStorage)).not.toContain("confidential");
    first.unmount();
    const second = renderWithIntl(
      <MatterAssistantScreen matterId="lost-synthetic" />,
    );
    await waitFor(() => expect(turns.latest).toHaveBeenCalledTimes(2));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "synthetic confidential wording" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(turns.send).toHaveBeenCalledTimes(2));
    expect(turns.send.mock.calls[1]?.[3]).toBe(key);
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: /New conversation/ })
          .hasAttribute("disabled"),
      ).toBe(false),
    );
    second.unmount();
  });

  it("recovers a failed saved attempt using the retry endpoint after reload", async () => {
    turns.latest.mockResolvedValue({
      ...succeeded,
      state: "failed",
      failureClass: "model_unavailable",
    });
    turns.retry.mockResolvedValue(succeeded);
    turns.read.mockResolvedValue(succeeded);
    renderWithIntl(<MatterConversation matterId="retry-synthetic" embedded />);
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    await waitFor(() => expect(turns.retry).toHaveBeenCalledTimes(1));
    expect(turns.send).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("renders the persisted executed proposal without offering a second confirmation", async () => {
    turns.messages.mockResolvedValue({
      items: [{ ...message, pendingActionId: "proposal" }],
      page: { hasMore: false },
    });
    turns.action.mockResolvedValue({
      id: "proposal",
      actionKind: "fact-accept",
      targetRef: "fact:synthetic",
      targetVersion: 3,
      state: "executed",
      arguments: {
        reviewed: {
          factValue: "Synthetic reviewed value",
          transactionId: "transaction-synthetic",
          subjectId: "subject-synthetic",
        },
      },
      result: { version: 4 },
    });
    renderWithIntl(
      <MatterConversation matterId="proposal-synthetic" embedded />,
    );
    await screen.findByText("Applied");
    expect(screen.getByText("Synthetic reviewed value")).toBeTruthy();
    expect(screen.getByText("subject-synthetic")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
  });

  it("shows exact retrieved passage and unverified case provenance after reload", async () => {
    turns.messages.mockResolvedValue({
      items: [
        {
          ...message,
          citations: [
            {
              sourceId: "SYN-CASE",
              sourceType: "case",
              label: "Synthetic case lead",
              verificationStatus: "unverified",
              locator: null,
              passage: "Synthetic retrieved passage",
              corpusVersion: "statutes-index-v1:" + "b".repeat(64),
            },
          ],
        },
      ],
      page: { hasMore: false },
    });
    renderWithIntl(
      <MatterConversation matterId="citation-synthetic" embedded />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: /Synthetic case lead/ }),
    );
    expect(
      screen.getAllByText("Synthetic retrieved passage").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Source version: statutes-index-v1:" + "b".repeat(64))
        .length,
    ).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Open source" })).toBeNull();
  });
});

describe("recorded work after interrupted responses", () => {
  it.each([true, false])(
    "keeps recorded work inspectable after reload (embedded=%s), with no automatic retry",
    async (embedded) => {
      turns.latest.mockResolvedValue({
        jobId: "partial-synthetic",
        state: "failed",
        toolCallCount: 1,
        failureClass: "model_unavailable",
      });
      turns.messages.mockResolvedValue({
        items: [
          {
            id: "recovery",
            sequence: 2,
            role: "assistant",
            content: "Recorded synthetic matter read before response stopped",
            jobId: "partial-synthetic",
            pendingActionId: null,
            citations: [
              {
                sourceId: "mat-synthetic",
                sourceType: "matter",
                label: "Synthetic recorded matter",
                verificationStatus: "operational",
                locator: null,
              },
            ],
          },
        ],
        page: { hasMore: false },
      });
      renderWithIntl(
        <MatterConversation matterId="mat-synthetic" embedded={embedded} />,
      );
      await screen.findByText(
        "Recorded synthetic matter read before response stopped",
      );
      await screen.findByRole("alert");
      expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
      fireEvent.click(
        screen.getByRole("button", { name: /Synthetic recorded matter/ }),
      );
      expect(
        screen
          .getAllByRole("link", { name: "Open source" })[0]
          ?.getAttribute("href"),
      ).toContain("source=mat-synthetic");
      expect(turns.send).not.toHaveBeenCalled();
      expect(turns.retry).not.toHaveBeenCalled();
      expect(
        screen.getByRole("heading", {
          level: embedded ? 2 : 1,
          name: "Matter assistant",
        }),
      ).toBeTruthy();
    },
  );

  it("keeps transcript visible when its proposal is unavailable, without a confirm control", async () => {
    turns.messages.mockResolvedValue({
      items: [
        {
          id: "record",
          role: "assistant",
          content: "Synthetic recorded proposal",
          citations: [],
          pendingActionId: "missing",
        },
      ],
      page: { hasMore: false },
    });
    turns.action.mockRejectedValue(new Error("unavailable"));
    renderWithIntl(<MatterConversation matterId="mat-synthetic" embedded />);
    await screen.findByText("Synthetic recorded proposal");
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
    expect(screen.getByTestId("proposal-card").textContent).toContain(
      "unavailable",
    );
  });

  it("refreshes a stale proposal after a rejected confirmation and never resubmits it", async () => {
    const card = {
      id: "proposal",
      actionKind: "checklist-decision",
      targetRef: "checklist-item:synthetic",
      targetVersion: 2,
      state: "proposed",
      arguments: { digitalReview: "LAWYER_CONFIRMED" },
      result: {},
    };
    turns.messages.mockResolvedValue({
      items: [
        {
          id: "record",
          role: "assistant",
          content: "Synthetic proposal",
          citations: [],
          pendingActionId: "proposal",
        },
      ],
      page: { hasMore: false },
    });
    turns.action
      .mockResolvedValueOnce(card)
      .mockResolvedValue({ ...card, state: "stale" });
    turns.confirm.mockRejectedValue(new Error("target changed"));
    renderWithIntl(<MatterConversation matterId="mat-synthetic" embedded />);
    fireEvent.click(await screen.findByRole("button", { name: "Confirm" }));
    await screen.findByText(/Changed since proposed/);
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
    expect(turns.confirm).toHaveBeenCalledTimes(1);
  });
});

describe("source and proposal recovery boundaries", () => {
  const record = {
    id: "source-message",
    role: "assistant",
    content: "Synthetic evidence answer",
    pendingActionId: null,
    citations: [],
  };
  it.each(["owned", "foreign", "unavailable"])(
    "opens original evidence only after a current matter check: %s",
    async (outcome) => {
      turns.messages.mockResolvedValue({
        items: [
          {
            ...record,
            citations: [
              {
                sourceId: "fact-synthetic",
                sourceType: "fact",
                label: "Synthetic evidence",
                verificationStatus: "verified",
                sourceFileId: "src-synthetic",
                page: 7,
              },
            ],
          },
        ],
        page: { hasMore: false },
      });
      if (outcome === "unavailable")
        turns.source.mockRejectedValue(new Error("unavailable"));
      else
        turns.source.mockResolvedValue({
          matterId: outcome === "owned" ? "mat-synthetic" : "foreign",
        });
      renderWithIntl(<MatterConversation matterId="mat-synthetic" embedded />);
      fireEvent.click(
        await screen.findByRole("button", { name: /Synthetic evidence$/ }),
      );
      expect(turns.source).not.toHaveBeenCalled();
      const panel = screen.getByRole("dialog", { name: "Matter context" });
      fireEvent.click(
        within(panel).getByRole("button", { name: "Open source" }),
      );
      if (outcome === "owned")
        expect(
          (await within(panel).findByTestId("original-preview")).textContent,
        ).toBe("src-synthetic:7");
      else {
        await within(panel).findByRole("alert");
        expect(within(panel).queryByTestId("original-preview")).toBeNull();
      }
      fireEvent.click(
        within(panel).getByRole("button", { name: "Back to matter context" }),
      );
      expect(within(panel).queryByTestId("original-preview")).toBeNull();
    },
  );

  it("leaves a legal citation without a saved passage explicitly unavailable", async () => {
    turns.messages.mockResolvedValue({
      items: [
        {
          ...record,
          citations: [
            {
              sourceId: "STAT-SYN",
              sourceType: "statute",
              label: "Synthetic authority",
              verificationStatus: "verified",
            },
          ],
        },
      ],
      page: { hasMore: false },
    });
    renderWithIntl(<MatterConversation matterId="mat-synthetic" embedded />);
    fireEvent.click(
      await screen.findByRole("button", { name: /Synthetic authority/ }),
    );
    expect(
      screen.getAllByText("The source passage is unavailable.").length,
    ).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Open source" })).toBeNull();
  });

  it.each([true, false])(
    "reloads the recorded decision after confirming=%s",
    async (confirm) => {
      const card = {
        id: "proposal",
        actionKind: "requirement-link",
        targetRef: "checklist-item:synthetic",
        targetVersion: 4,
        state: "proposed",
        arguments: {
          detectedDocumentId: "doc-synthetic",
          documentVersion: 2,
          interpretationGeneration: 3,
          evidenceReferenceIds: ["evidence-synthetic"],
          reason: "Synthetic review reason",
        },
        result: {},
      };
      turns.messages.mockResolvedValue({
        items: [{ ...record, pendingActionId: "proposal" }],
        page: { hasMore: false },
      });
      turns.action.mockResolvedValueOnce(card).mockResolvedValue({
        ...card,
        state: confirm ? "executed" : "declined",
        result: confirm ? { linkId: "link-synthetic" } : {},
      });
      turns.confirm.mockResolvedValue({});
      turns.reject.mockResolvedValue({});
      renderWithIntl(<MatterConversation matterId="mat-synthetic" embedded />);
      fireEvent.click(
        await screen.findByRole("button", {
          name: confirm ? "Confirm" : "Reject",
        }),
      );
      await screen.findByText(confirm ? "Applied" : "Declined", {
        exact: true,
      });
      expect(confirm ? turns.confirm : turns.reject).toHaveBeenCalledTimes(1);
      expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
      if (confirm)
        expect(
          screen.getByText(/Recorded result: link-synthetic/),
        ).toBeTruthy();
    },
  );

  it("starts a fresh segment once, and clears preceding retry and transcript state", async () => {
    turns.latest.mockResolvedValue({
      jobId: "old",
      state: "failed",
      toolCallCount: 0,
      failureClass: "model_unavailable",
    });
    turns.messages.mockResolvedValue({
      items: [record],
      page: { hasMore: false },
    });
    turns.fresh.mockResolvedValue({ id: "new-conversation" });
    const prompt = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderWithIntl(<MatterConversation matterId="mat-synthetic" embedded />);
    await screen.findByRole("button", { name: "Try again" });
    fireEvent.click(screen.getByRole("button", { name: /New conversation/ }));
    await waitFor(() => expect(screen.queryByText(record.content)).toBeNull());
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    expect(turns.fresh).toHaveBeenCalledTimes(1);
    expect(turns.send).not.toHaveBeenCalled();
    prompt.mockRestore();
  });
});

describe("conversation refusal and navigation", () => {
  it.each([
    ["pending_action_stale", "errorStale"],
    ["capability_denied", "errorCapability"],
    ["matter_agent_disabled", "errorDisabled"],
    ["agent_model_unavailable", "errorProvider"],
    ["agent_retry_unavailable", "errorRetry"],
  ] as const)(
    "shows the current %s refusal without starting a provider turn",
    async (code, key) => {
      turns.latest.mockRejectedValue(
        new ApiError(503, code, "Synthetic error", "synthetic-correlation", {}),
      );
      renderWithIntl(
        <MatterConversation matterId="refusal-synthetic" embedded />,
      );
      expect((await screen.findByRole("alert")).textContent).toContain(
        messages.matterAssistant[key],
      );
      expect(turns.send).not.toHaveBeenCalled();
      expect(turns.retry).not.toHaveBeenCalled();
    },
  );

  it("reads older saved messages without replacing the newer page or sending again", async () => {
    const newer = {
      id: "newer",
      role: "assistant",
      content: "Synthetic newer response",
      pendingActionId: null,
      citations: [],
    };
    turns.messages
      .mockResolvedValueOnce({
        items: [newer],
        page: { hasMore: true, nextCursor: "older-cursor" },
      })
      .mockResolvedValue({
        items: [{ ...newer, id: "older", content: "Synthetic older response" }],
        page: { hasMore: false, nextCursor: null },
      });
    renderWithIntl(
      <MatterConversation matterId="history-synthetic" embedded />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Load older messages" }),
    );
    await screen.findByText("Synthetic older response");
    expect(screen.getByText(newer.content)).toBeTruthy();
    expect(turns.messages).toHaveBeenLastCalledWith(
      turns.token,
      "history-synthetic",
      { limit: 20, cursor: "older-cursor" },
    );
    expect(turns.send).not.toHaveBeenCalled();
  });

  it("opens only a supported inline citation and traps/restores narrow-panel keyboard focus", async () => {
    turns.messages.mockResolvedValue({
      items: [
        {
          id: "inline",
          role: "assistant",
          content: "Synthetic answer [1]. Unsupported marker [2].",
          pendingActionId: null,
          citations: [
            {
              sourceId: "AUTH-SYN",
              sourceType: "statute",
              label: "Synthetic authority",
              verificationStatus: "verified",
              passage: "Synthetic saved passage",
            },
          ],
        },
      ],
      page: { hasMore: false },
    });
    renderWithIntl(
      <MatterConversation matterId="keyboard-synthetic" embedded />,
    );
    const citation = await screen.findByRole("button", {
      name: "Synthetic authority, Verified",
    });
    citation.focus();
    fireEvent.click(citation);
    const panel = screen.getByRole("dialog", { name: "Matter context" });
    const controls = within(panel).getAllByRole("button");
    const first = controls[0]!;
    const last = controls.at(-1)!;
    first.focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    fireEvent.keyDown(window, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    expect(within(panel).getByText("Synthetic saved passage")).toBeTruthy();
    expect(within(panel).getByText("Matched source passage")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "[2]" })).toBeNull();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(citation);
  });
});

it("shows a new turn's recorded work after tool failure without offering a duplicate retry", async () => {
  const failed = {
    jobId: "new-partial",
    state: "failed",
    toolCallCount: 1,
    failureClass: "model_unavailable",
  };
  turns.send.mockResolvedValue(failed);
  turns.read.mockResolvedValue(failed);
  turns.messages
    .mockResolvedValueOnce({ items: [], page: { hasMore: false } })
    .mockResolvedValue({
      items: [
        {
          id: "recovered",
          role: "assistant",
          content: "Synthetic recorded work from this request",
          pendingActionId: null,
          citations: [],
        },
      ],
      page: { hasMore: false },
    });
  renderWithIntl(
    <MatterConversation matterId="new-partial-synthetic" embedded />,
  );
  await waitFor(() => expect(turns.latest).toHaveBeenCalled());
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "Synthetic request" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    messages.matterAssistant.turnFailedAfterTools,
  );
  expect(
    screen.getByText("Synthetic recorded work from this request"),
  ).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  expect(turns.send).toHaveBeenCalledTimes(1);
  expect(turns.retry).not.toHaveBeenCalled();
});

it.each(["succeeded", "running"])(
  "retires an exactly accepted lost-response intent after remount (%s)",
  async (state) => {
    const matterId = `accepted-lost-${state}`;
    const completed = {
      jobId: "accepted-job",
      state: "succeeded",
      toolCallCount: 0,
      failureClass: null,
    };
    turns.send
      .mockRejectedValueOnce(new Error("lost accepted response"))
      .mockResolvedValue(completed);
    turns.read.mockResolvedValue(completed);
    const first = renderWithIntl(
      <MatterConversation matterId={matterId} embedded />,
    );
    await waitFor(() => expect(turns.latest).toHaveBeenCalled());
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Synthetic what is missing?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("alert");
    const oldKey = turns.send.mock.calls[0]?.[3];
    first.unmount();
    turns.latest.mockResolvedValue({ ...completed, state });
    turns.receipt.mockResolvedValue({
      sendKey: oldKey,
      matterId,
      conversationId: "conv-1",
      jobId: completed.jobId,
    });
    renderWithIntl(<MatterAssistantScreen matterId={matterId} />);
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: /New conversation/ })
          .hasAttribute("disabled"),
      ).toBe(false),
    );
    await waitFor(() => expect(turns.latest).toHaveBeenCalledTimes(2));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Synthetic what is missing?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(turns.send).toHaveBeenCalledTimes(2));
    expect(turns.send.mock.calls[1]?.[3]).not.toBe(oldKey);
  },
);

it.each(["en", "si"] as const)(
  "localizes review decisions and citation accessibility status in %s",
  async (locale) => {
    const catalogue = locale === "en" ? messages : sinhala;
    turns.messages.mockResolvedValue({
      items: [
        {
          id: "localized",
          role: "assistant",
          content: "Synthetic citation [1]",
          pendingActionId: "localized-action",
          citations: [
            {
              sourceId: "synthetic",
              sourceType: "fact",
              label: "Synthetic source",
              verificationStatus: "verified",
            },
          ],
        },
      ],
      page: { hasMore: false },
    });
    turns.action.mockResolvedValue({
      id: "localized-action",
      actionKind: "checklist-decision",
      state: "executed",
      arguments: { digitalReview: "LAWYER_CONFIRMED" },
      result: {},
    });
    renderWithIntl(
      <MatterConversation matterId={`localized-${locale}`} embedded />,
      locale,
    );
    await screen.findByRole("button", {
      name: `Synthetic source, ${catalogue.matterAssistant.verification.verified}`,
    });
    expect(screen.getByTestId("proposal-card").textContent).toContain(
      catalogue.enums.requirementStatus.LAWYER_CONFIRMED,
    );
    expect(screen.getByTestId("proposal-card").textContent).not.toContain(
      "LAWYER_CONFIRMED",
    );
  },
);

it.each(["matter", "conversation", "key", "missing-job", "unavailable"])(
  "preserves a pending send when receipt is %s",
  async (mismatch) => {
    const matterId = `unproven-${mismatch}`;
    const completed = {
      jobId: "accepted-other-job",
      state: "succeeded",
      toolCallCount: 0,
      failureClass: null,
    };
    turns.send
      .mockRejectedValueOnce(new Error("lost response"))
      .mockResolvedValue(completed);
    turns.read.mockResolvedValue(completed);
    const first = renderWithIntl(
      <MatterConversation matterId={matterId} embedded />,
    );
    await waitFor(() => expect(turns.latest).toHaveBeenCalled());
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Synthetic same question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("alert");
    const key = turns.send.mock.calls[0]?.[3];
    first.unmount();
    if (mismatch === "unavailable")
      turns.receipt.mockRejectedValue(new Error("unavailable"));
    else
      turns.receipt.mockResolvedValue({
        matterId: mismatch === "matter" ? "foreign" : matterId,
        conversationId: mismatch === "conversation" ? "foreign" : "conv-1",
        sendKey: mismatch === "key" ? "foreign" : key,
        jobId: mismatch === "missing-job" ? "" : completed.jobId,
      });
    renderWithIntl(<MatterAssistantScreen matterId={matterId} />);
    await waitFor(() => expect(turns.latest).toHaveBeenCalledTimes(2));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Synthetic same question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(turns.send).toHaveBeenCalledTimes(2));
    expect(turns.send.mock.calls[1]?.[3]).toBe(key);
  },
);
