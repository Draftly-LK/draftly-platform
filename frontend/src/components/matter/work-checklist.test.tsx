// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { WorkChecklist } from "./work-checklist";

const mocks = vi.hoisted(() => ({
  fail: false,
  conflict: false,
  keys: [] as string[],
  loaded: 0,
  packet: {} as Record<string, unknown>,
  decision: null as unknown,
  historyRead: null as Promise<unknown> | null,
  evidenceRead: null as Promise<unknown> | null,
}));
vi.mock("@/lib/api/auth", () => ({
  getMe: async () => ({ id: "synthetic-actor" }),
}));
vi.mock("@/lib/api/work-checklist", async () => {
  const { ApiError } = await import("@/lib/api/client");
  return {
    getWorkChecklist: async () => {
      mocks.loaded++;
      return mocks.packet;
    },
    createWorkTask: async (
      _token: unknown,
      _matter: unknown,
      body: { title: string },
      key: string,
    ) => {
      mocks.keys.push(key);
      if (mocks.fail) throw new Error("synthetic network failure");
      mocks.packet.tasks = [
        ...(mocks.packet.tasks as object[]),
        task("added", { title: body.title }),
      ];
    },
    decideWorkTask: async (
      _token: unknown,
      _matter: unknown,
      _id: unknown,
      body: unknown,
      _version: unknown,
      key: string,
    ) => {
      mocks.keys.push(key);
      mocks.decision = body;
      if (mocks.conflict)
        throw new ApiError(
          412,
          "precondition_failed",
          "synthetic conflict",
          "",
          {},
        );
      if (mocks.fail) throw new Error("synthetic network failure");
    },
    decideTaskSuggestion: async () => {
      mocks.packet.suggestions = [];
    },
    getWorkTaskHistory: async () =>
      mocks.historyRead ?? {
        items: [
          {
            id: "event",
            decision: "complete",
            actorId: "synthetic-lawyer",
            createdAt: "2026-10-09T10:00:00Z",
            note: "Synthetic supporting record",
          },
        ],
        nextCursor: null,
      },
  };
});
vi.mock("@/lib/api/documents", () => ({
  getCompleteDocumentInbox: async () =>
    mocks.evidenceRead ?? {
      sourceFiles: [
        {
          id: "source-synthetic",
          originalFilename: "Synthetic signing record.pdf",
          version: 3,
          supersededBySourceFileId: null,
        },
      ],
      documents: [
        { id: "document-synthetic", version: 2, interpretationGeneration: 4 },
      ],
    },
}));
const token = async () => "synthetic-token";
function task(id: string, changes: object = {}) {
  return {
    id,
    version: 1,
    group: "documents",
    origin: "lawyer",
    state: "not-started",
    title: "Review synthetic parcel mismatch",
    titleKey: null,
    reason: "Two source records disagree",
    reasonKey: null,
    completedBy: null,
    completedAt: null,
    assignedTo: null,
    evidence: [],
    action: { kind: "decide", section: null, targetId: null },
    ...changes,
  };
}
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  sessionStorage.clear();
  mocks.fail = false;
  mocks.conflict = false;
  mocks.keys = [];
  mocks.loaded = 0;
  mocks.decision = null;
  mocks.historyRead = null;
  mocks.evidenceRead = null;
  mocks.packet = {
    matterId: "synthetic",
    tasks: [
      task("open"),
      task("complete", {
        title: "Synthetic processing",
        state: "complete",
        origin: "operational",
        action: null,
        completedBy: "document-service",
        completedAt: "2026-10-09T09:00:00Z",
      }),
    ],
    suggestions: [],
    progress: { total: 2, completed: 1, percent: 50, assessing: true },
    nextTaskId: "open",
  };
});
it("shows recorded completion and assessment uncertainty without implying approval", async () => {
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  expect(await screen.findByRole("progressbar")).toHaveProperty("value", 50);
  expect(screen.getByText("Checklist still being assessed")).toBeTruthy();
  expect(screen.getByText(/Approval and export eligibility/)).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Record completion" }),
  ).toBeTruthy();
  expect(
    screen.getByText("Synthetic processing").closest("details")?.open,
  ).toBe(false);
  fireEvent.click(screen.getByText("Completed and inactive tasks (1)"));
  expect(screen.getByText("Synthetic processing")).toBeTruthy();
});
it("links the next governed action to the existing matter screen", async () => {
  mocks.packet.tasks = [
    task("open", {
      origin: "governed",
      action: { kind: "navigate", section: "facts", targetId: null },
    }),
  ];
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  expect(
    (await screen.findAllByRole("link", { name: "Review" }))[0]?.getAttribute(
      "href",
    ),
  ).toBe("/matters/synthetic/facts");
  expect(screen.queryByRole("button", { name: "Complete task" })).toBeNull();
});
it("retries an uncertain create with the same logical key and retains input", async () => {
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  fireEvent.click(await screen.findByRole("button", { name: "Add task" }));
  fireEvent.change(screen.getByLabelText("Task"), {
    target: { value: "Collect synthetic supporting record" },
  });
  mocks.fail = true;
  fireEvent.click(screen.getByRole("button", { name: "Save task" }));
  await screen.findByRole("alert");
  expect((screen.getByLabelText("Task") as HTMLInputElement).value).toBe(
    "Collect synthetic supporting record",
  );
  mocks.fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Save task" }));
  await screen.findByText("Collect synthetic supporting record");
  expect(mocks.keys).toHaveLength(2);
  expect(mocks.keys[1]).toBe(mocks.keys[0]);
});
it("requires deliberate refresh after a changed task and retains previous history", async () => {
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Record completion" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "View history" }));
  await screen.findByText("Synthetic supporting record");
  mocks.conflict = true;
  fireEvent.click(screen.getByRole("button", { name: "Complete task" }));
  await screen.findByRole("alert");
  expect(
    (screen.getByRole("button", { name: "Complete task" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  mocks.conflict = false;
  fireEvent.click(screen.getByRole("button", { name: "Refresh checklist" }));
  await waitFor(() =>
    expect(
      (
        screen.getByRole("button", {
          name: "Complete task",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false),
  );
});
it("keeps agent suggestions outside progress until lawyer acceptance", async () => {
  mocks.packet.suggestions = [
    task("suggestion", {
      title: "Review synthetic plan record",
      origin: "agent",
    }),
  ];
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Accept suggestion" }),
  );
  await waitFor(() =>
    expect(screen.queryByText("Review synthetic plan record")).toBeNull(),
  );
  expect(screen.getByRole("progressbar")).toHaveProperty("value", 50);
});
it("renders the checklist controls in Sinhala", async () => {
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />, "si");
  expect(await screen.findByRole("progressbar")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Add task" })).toBeNull();
});
it("retains an uncertain create key across refresh instead of duplicating the task", async () => {
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  fireEvent.click(await screen.findByRole("button", { name: "Add task" }));
  fireEvent.change(screen.getByLabelText("Task"), {
    target: { value: "Synthetic follow-up record" },
  });
  mocks.fail = true;
  fireEvent.click(screen.getByRole("button", { name: "Save task" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Refresh checklist" }));
  await waitFor(() =>
    expect(
      (screen.getByRole("button", { name: "Save task" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false),
  );
  mocks.fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Save task" }));
  await screen.findByText("Synthetic follow-up record");
  expect(mocks.keys[1]).toBe(mocks.keys[0]);
});
it("records completion against the selected document interpretation without creating legal readiness", async () => {
  mocks.packet.tasks = [
    task("work:synthetic:execution", {
      origin: "operational",
      group: "execution",
      title: "Review synthetic signing",
    }),
  ];
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Record completion" }),
  );
  expect(screen.getByText(/does not create an approval/)).toBeTruthy();
  expect(
    (screen.getByRole("button", { name: "Complete task" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  fireEvent.click(
    screen.getByRole("button", { name: "Link supporting document" }),
  );
  fireEvent.click(
    await screen.findByRole("checkbox", { name: "Document 1 · Version 2" }),
  );
  fireEvent.change(screen.getByLabelText("Decision note"), {
    target: { value: "Synthetic signing record reviewed" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Complete task" }));
  await waitFor(() =>
    expect(mocks.decision).toEqual({
      decision: "complete",
      note: "Synthetic signing record reviewed",
      evidence: [
        {
          kind: "document",
          id: "document-synthetic",
          version: 2,
          generation: 4,
          transactionId: null,
          subjectId: null,
          associationVersion: null,
        },
      ],
    }),
  );
});
it("opens the supporting detected document directly instead of sending the lawyer to the inbox", async () => {
  mocks.packet.tasks = [
    task("open", {
      evidence: [
        {
          kind: "document",
          id: "document / synthetic",
          version: 2,
          generation: 4,
          transactionId: null,
          subjectId: null,
          associationVersion: null,
        },
      ],
    }),
  ];
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  expect(
    (
      await screen.findByRole("link", {
        name: "Supporting evidence 1 · Version 2",
      })
    ).getAttribute("href"),
  ).toBe("/matters/synthetic/documents/document%20%2F%20synthetic/review");
});
it("finishes overlapping history and evidence reads independently", async () => {
  let historyDone!: (value: unknown) => void;
  let evidenceDone!: (value: unknown) => void;
  mocks.historyRead = new Promise((resolve) => {
    historyDone = resolve;
  });
  mocks.evidenceRead = new Promise((resolve) => {
    evidenceDone = resolve;
  });
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Record completion" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "View history" }));
  fireEvent.click(
    screen.getByRole("button", { name: "Link supporting document" }),
  );
  historyDone({ items: [], nextCursor: null });
  evidenceDone({ sourceFiles: [], documents: [] });
  await waitFor(() => {
    expect(
      (
        screen.getByRole("button", {
          name: "View history",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
    expect(
      (
        screen.getByRole("button", {
          name: "Link supporting document",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  });
  expect(screen.getByText("No decisions recorded yet")).toBeTruthy();
});
it("retains accepted suggestion source pins when completing and shows renewed review after a source change", async () => {
  const evidence = [
    {
      kind: "source",
      id: "source-synthetic",
      version: 3,
      generation: null,
      transactionId: null,
      subjectId: null,
      associationVersion: null,
    },
  ];
  mocks.packet.tasks = [task("agent-task", { origin: "agent", evidence })];
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Record completion" }),
  );
  expect(
    (
      screen.getByRole("checkbox", {
        name: "Supporting evidence 1",
      }) as HTMLInputElement
    ).checked,
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Complete task" }));
  await waitFor(() =>
    expect(mocks.decision).toEqual({ decision: "complete", evidence }),
  );
  mocks.packet = {
    ...mocks.packet,
    tasks: [
      task("agent-task", {
        origin: "agent",
        evidence,
        state: "stale",
        version: 2,
      }),
    ],
    progress: { total: 1, completed: 0, percent: 0, assessing: false },
  };
  fireEvent.click(screen.getByRole("button", { name: "Refresh checklist" }));
  await waitFor(() =>
    expect(screen.getByRole("progressbar")).toHaveProperty("value", 0),
  );
  expect(screen.getByText("Needs review")).toBeTruthy();
});
it("uses localized suggestion keys when the agent also supplies English fallback text", async () => {
  mocks.packet.suggestions = [
    task("suggestion", {
      title: "Upload and process source documents",
      titleKey: "matterChecklist.tasks.documents.title",
      reason: "English fallback reason",
      reasonKey: "matterChecklist.tasks.documents.reason",
      origin: "agent",
    }),
  ];
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />, "si");
  expect(await screen.findByText("මූලාශ්‍ර ලේඛන උඩුගත කර සකසන්න")).toBeTruthy();
  expect(screen.queryByText("English fallback reason")).toBeNull();
});
it("renews a stale task with the lawyer's selected replacement source instead of keeping the superseded original", async () => {
  const old = {
    kind: "source",
    id: "source-old-synthetic",
    version: 1,
    generation: null,
    transactionId: null,
    subjectId: null,
    associationVersion: null,
  };
  mocks.packet.tasks = [
    task("stale-agent", { state: "stale", origin: "agent", evidence: [old] }),
  ];
  renderWithIntl(<WorkChecklist matterId="synthetic" getToken={token} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Record completion" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Link supporting document" }),
  );
  fireEvent.click(
    await screen.findByRole("checkbox", {
      name: "Synthetic signing record.pdf",
    }),
  );
  fireEvent.click(
    screen.getByRole("checkbox", { name: "Supporting evidence 1" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Review current evidence" }),
  );
  await waitFor(() =>
    expect(mocks.decision).toEqual({
      decision: "review",
      evidence: [
        {
          kind: "source",
          id: "source-synthetic",
          version: 3,
          generation: null,
          transactionId: null,
          subjectId: null,
          associationVersion: null,
        },
      ],
    }),
  );
});
