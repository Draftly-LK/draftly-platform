import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  auditEvents as seededEvents,
  checks as seededChecks,
  DEMO_MATTER_ID,
  DEMO_USER_ID,
  documents as seededDocuments,
  drafts as seededDrafts,
  facts as seededFacts,
  matters as seededMatters,
  workflows as seededWorkflows,
} from "@/lib/mocks";
import type { EditorDocument } from "@/types";
import { useDemoStore } from "./demo-store";

// Node has no localStorage, and without one zustand skips `persist` entirely,
// migrations included. This must run before the store module loads.
vi.hoisted(() => {
  const items = new Map<string, string>();
  globalThis.localStorage = {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
    removeItem: (key: string) => void items.delete(key),
    clear: () => items.clear(),
    key: (index: number) => [...items.keys()][index] ?? null,
    get length() {
      return items.size;
    },
  };
});

// The store is the frontend's offline state machine (TESTING_PLAN.md F10).
// Every action must leave the state it promises and append one audit event.

/** The first item, failing loudly if a fixture list is ever empty. */
function head<T>(items: readonly T[] | undefined): T {
  const [item] = items ?? [];
  if (item === undefined) throw new Error("expected at least one item");
  return item;
}

const store = () => useDemoStore.getState();
const lastEvent = () => store().auditEvents.at(-1);
const TEMPLATE_ID = "template-form8-001";
const DRAFT_ID = head(seededDrafts).id;
const FACT_ID = "fact-district";
const EMPTY_DOC: EditorDocument = { type: "doc", content: [] };

beforeEach(() => {
  store().resetDemo();
});

describe("resetDemo", () => {
  it("restores every seeded collection exactly", () => {
    store().createMatter({ reference: "SYN/0009", regime: "rta", type: "transfer" });
    store().verifyFact("fact-district");

    store().resetDemo();

    expect(store().matters).toEqual(seededMatters);
    expect(store().documents).toEqual(seededDocuments);
    expect(store().facts).toEqual(seededFacts);
    expect(store().checks).toEqual(seededChecks);
    expect(store().workflows).toEqual(seededWorkflows);
    expect(store().drafts).toEqual(seededDrafts);
  });

  it("keeps the seeded history and records the reset itself", () => {
    const events = store().auditEvents;

    expect(events.slice(0, -1)).toEqual(seededEvents);
    expect(events.at(-1)).toMatchObject({ id: "audit-reset", action: "demo.reset" });
  });

  it("does not share objects with the fixtures", () => {
    store().correctFact(FACT_ID, "Synthetic district", "Synthetic reason");

    expect(seededFacts.find((fact) => fact.id === FACT_ID)?.value).toBe("Colombo");
  });
});

describe("audit events", () => {
  it("are numbered and timed from the event count, never the clock", () => {
    const count = store().auditEvents.length;

    store().verifyFact(FACT_ID);

    expect(lastEvent()).toMatchObject({
      id: `audit-live-${String(count + 1).padStart(3, "0")}`,
      actor: DEMO_USER_ID,
      timestamp: new Date(Date.UTC(2026, 6, 22, 10, count, 0)).toISOString(),
    });
  });

  it("replay identically from the same starting state", () => {
    const run = () => {
      store().resetDemo();
      store().createMatter({ reference: "SYN/0001", regime: "rta", type: "transfer" });
      store().addDocument("synthetic.pdf");
      return structuredClone(store().auditEvents);
    };

    expect(run()).toEqual(run());
  });
});

describe("createMatter", () => {
  it("adds an open matter and copies the demo facts and checks onto it", () => {
    const demoFacts = store().facts.filter((f) => f.matterId === DEMO_MATTER_ID);
    const demoChecks = store().checks.filter((c) => c.matterId === DEMO_MATTER_ID);

    const id = store().createMatter({
      reference: "SYN/0001",
      regime: "rta",
      type: "transfer",
    });

    const matter = store().matters.find((m) => m.id === id);
    expect(matter).toMatchObject({ reference: "SYN/0001", status: "open", ownerId: DEMO_USER_ID });
    expect(store().facts.filter((f) => f.matterId === id)).toHaveLength(demoFacts.length);
    expect(store().checks.filter((c) => c.matterId === id)).toHaveLength(demoChecks.length);
    expect(lastEvent()).toMatchObject({ action: "matter.created", targetId: id, matterId: id });
  });

  it("points copied checks at the copied facts, not the originals", () => {
    const id = store().createMatter({ reference: "SYN/0001", regime: "rta", type: "transfer" });

    const copiedFactIds = new Set(store().facts.filter((f) => f.matterId === id).map((f) => f.id));
    for (const check of store().checks.filter((c) => c.matterId === id)) {
      for (const factId of check.affectedFactIds) {
        if (factId.startsWith("fact-")) continue; // not a demo fact: left as is
        expect(copiedFactIds.has(factId)).toBe(true);
      }
    }
  });

  it("gives each new matter its own id", () => {
    const first = store().createMatter({ reference: "SYN/0001", regime: "rta", type: "transfer" });
    const second = store().createMatter({ reference: "SYN/0002", regime: "rta", type: "transfer" });

    expect(first).not.toBe(second);
  });
});

describe("source files", () => {
  it("addDocument stops at STORED and records the upload", () => {
    const id = store().addDocument("synthetic-deed.pdf", "deed");

    const document = store().documents.find((d) => d.id === id);
    expect(document).toMatchObject({
      fileName: "synthetic-deed.pdf",
      kind: "deed",
      matterId: DEMO_MATTER_ID,
      processingState: "STORED",
      versionRelationship: "CURRENT",
    });
    expect(document?.sha256).toMatch(/^syn-sha256-[0-9a-f]{8}$/);
    expect(lastEvent()).toMatchObject({ action: "document.uploaded", targetId: id });
  });

  it("addDocument gives the same bytes the same synthetic digest", () => {
    const id = store().addDocument("synthetic.pdf");
    const digest = store().documents.find((d) => d.id === id)?.sha256;

    store().resetDemo();
    store().addDocument("synthetic.pdf");

    expect(store().documents.find((d) => d.id === id)?.sha256).toBe(digest);
  });

  it("markProcessingNotConfigured fails the run with a recoverable reason", () => {
    const id = store().addDocument("synthetic.pdf");

    store().markProcessingNotConfigured(id);

    expect(store().documents.find((d) => d.id === id)).toMatchObject({
      processingState: "PROCESSING_FAILED",
      failureReason: "NOT_CONFIGURED",
    });
    expect(lastEvent()).toMatchObject({
      action: "source-file.processing-not-configured",
      targetId: id,
    });
  });

  it("no client action ever claims PROCESSED", () => {
    const id = store().addDocument("synthetic.pdf");
    store().markProcessingNotConfigured(id);
    store().replaceDocument(id, "synthetic-2.pdf", "Synthetic rescan");

    expect(store().documents.find((d) => d.id === id)?.processingState).not.toBe("PROCESSED");
  });

  it("replaceDocument keeps the old version and clears the failure", () => {
    const id = store().addDocument("synthetic.pdf");
    store().markProcessingNotConfigured(id);
    const before = store().documents.find((d) => d.id === id);

    store().replaceDocument(id, "synthetic-rescan.pdf", "Synthetic rescan");

    const after = store().documents.find((d) => d.id === id);
    expect(after).toMatchObject({ fileName: "synthetic-rescan.pdf", processingState: "STORED" });
    expect(after?.failureReason).toBeUndefined();
    expect(after?.versions.at(-1)).toMatchObject({ reason: "Synthetic rescan" });
    expect(after?.sha256).not.toBe(before?.sha256);
    expect(lastEvent()).toMatchObject({ action: "document.replaced", before });
  });
});

describe("facts", () => {
  it("verifyFact records the reviewer and the before/after", () => {
    store().verifyFact(FACT_ID);

    const fact = store().facts.find((f) => f.id === FACT_ID);
    expect(fact).toMatchObject({ verificationState: "verified", reviewerId: DEMO_USER_ID });
    expect(lastEvent()).toMatchObject({ action: "fact.verified", targetId: FACT_ID, after: fact });
  });

  it("correctFact changes the value and keeps the old one in its history", () => {
    store().correctFact(FACT_ID, "Synthetic district", "Synthetic reason");

    const fact = store().facts.find((f) => f.id === FACT_ID);
    expect(fact).toMatchObject({ value: "Synthetic district", verificationState: "corrected" });
    expect(fact?.changes.at(-1)).toMatchObject({
      before: "Colombo",
      after: "Synthetic district",
      reason: "Synthetic reason",
      actorId: DEMO_USER_ID,
    });
    expect(lastEvent()).toMatchObject({ action: "fact.corrected", targetId: FACT_ID });
  });

  it("addManualFact starts unreviewed, however sure the lawyer is", () => {
    const id = store().addManualFact("facts.synthetic", "Synthetic value", "Synthetic reason");

    expect(store().facts.find((f) => f.id === id)).toMatchObject({
      verificationState: "unreviewed",
      manualReason: "Synthetic reason",
      extractedValue: null,
      matterId: DEMO_MATTER_ID,
    });
    expect(lastEvent()).toMatchObject({ action: "fact.added-manually", targetId: id });
  });
});

describe("checks and workflow", () => {
  it("resolveCheck records who resolved it, why, and the action", () => {
    const checkId = head(seededChecks).id;

    store().resolveCheck(checkId, "waived", "Synthetic reason");

    expect(store().checks.find((c) => c.id === checkId)).toMatchObject({
      status: "pass",
      resolution: { action: "waived", reason: "Synthetic reason", actorId: DEMO_USER_ID },
    });
    expect(lastEvent()).toMatchObject({ action: "check.waived", targetId: checkId });
  });

  it("completeStep marks the step complete", () => {
    const workflow = head(seededWorkflows);
    const stepId = head(workflow.steps).id;

    store().completeStep(workflow.id, stepId, "Synthetic note");

    const step = store()
      .workflows.find((w) => w.id === workflow.id)
      ?.steps.find((s) => s.id === stepId);
    expect(step).toMatchObject({ state: "complete", note: "Synthetic note" });
    expect(lastEvent()).toMatchObject({ action: "workflow.step-completed", targetId: stepId });
  });

  it("an override is audited as an override, with its reason", () => {
    const workflow = head(seededWorkflows);
    const stepId = head(workflow.steps).id;

    store().completeStep(workflow.id, stepId, undefined, "Synthetic override");

    expect(lastEvent()).toMatchObject({
      action: "workflow.step-overridden",
      after: { overrideReason: "Synthetic override" },
    });
  });
});

describe("drafts", () => {
  it("createDraft refuses an unknown template", () => {
    const count = store().auditEvents.length;

    expect(store().createDraft(DEMO_MATTER_ID, "template-synthetic")).toBeNull();
    expect(store().auditEvents).toHaveLength(count);
  });

  it("createDraft refuses a matter whose facts are not all reviewed", () => {
    const count = store().drafts.length;

    expect(store().createDraft(DEMO_MATTER_ID, TEMPLATE_ID)).toBeNull();
    expect(store().createDraft("matter-synthetic-empty", TEMPLATE_ID)).toBeNull();
    expect(store().drafts).toHaveLength(count);
  });

  it("createDraft builds a working draft at version 1", () => {
    for (const fact of store().facts.filter((f) => f.matterId === DEMO_MATTER_ID)) {
      store().verifyFact(fact.id);
    }

    const id = store().createDraft(DEMO_MATTER_ID, TEMPLATE_ID);
    expect(id).not.toBeNull();

    const draft = store().drafts.find((d) => d.id === id);
    expect(draft).toMatchObject({ approvalState: "working", activeVersionId: `${id}-v1` });
    expect(draft?.versions).toHaveLength(1);
    expect(lastEvent()).toMatchObject({ action: "draft.created", targetId: id });
  });

  it("saveDraftVersion appends a version and makes it active", () => {
    const before = store().drafts.find((d) => d.id === DRAFT_ID);

    store().saveDraftVersion(DRAFT_ID, EMPTY_DOC);

    const draft = store().drafts.find((d) => d.id === DRAFT_ID);
    expect(draft?.versions).toHaveLength((before?.versions.length ?? 0) + 1);
    expect(draft?.activeVersionId).toBe(draft?.versions.at(-1)?.id);
    expect(draft?.versions.at(-1)?.document).toEqual(EMPTY_DOC);
    expect(lastEvent()).toMatchObject({ action: "draft.version-created", targetId: DRAFT_ID });
  });

  it("restoreDraftVersion copies the old version forward, never rewinds", () => {
    const first = head(head(seededDrafts).versions);
    store().approveDraft(DRAFT_ID);

    store().restoreDraftVersion(DRAFT_ID, first.id);

    const draft = store().drafts.find((d) => d.id === DRAFT_ID);
    const restored = draft?.versions.at(-1);
    expect(draft?.versions).toHaveLength(head(seededDrafts).versions.length + 1);
    expect(restored).toMatchObject({ restoredFromVersionId: first.id, document: first.document });
    expect(draft?.activeVersionId).toBe(restored?.id);
    // A restore is new content, so any approval no longer applies.
    expect(draft?.approvalState).toBe("working");
    expect(lastEvent()).toMatchObject({ action: "draft.version-restored" });
  });

  it("restoreDraftVersion of an unknown version changes no draft", () => {
    store().restoreDraftVersion(DRAFT_ID, "draftver-synthetic");

    expect(store().drafts).toEqual(seededDrafts);
  });

  it("approveDraft records the approver", () => {
    store().approveDraft(DRAFT_ID);

    expect(store().drafts.find((d) => d.id === DRAFT_ID)).toMatchObject({
      approvalState: "approved",
      approvedBy: DEMO_USER_ID,
    });
    expect(lastEvent()).toMatchObject({ action: "draft.approved", targetId: DRAFT_ID });
  });

  it("exportDraft of an approved draft exports it and names the format", () => {
    store().approveDraft(DRAFT_ID);

    store().exportDraft(DRAFT_ID, "pdf");

    expect(store().drafts.find((d) => d.id === DRAFT_ID)?.approvalState).toBe("exported");
    expect(lastEvent()).toMatchObject({ action: "draft.exported-pdf", after: { format: "pdf" } });
  });

  it("refusal 3: exportDraft before approveDraft is refused", () => {
    const count = store().auditEvents.length;

    store().exportDraft(DRAFT_ID, "docx");

    expect(store().drafts.find((d) => d.id === DRAFT_ID)?.approvalState).toBe("in-review");
    expect(store().auditEvents).toHaveLength(count);
  });

  // Appendix A refusal 2. The store has no "stale" draft state at all
  // (DraftApprovalState), so a correction leaves an approved draft approved.
  // The server enforces this (draft staleness §10.7); the demo does not yet.
  it.fails("refusal 2: correcting a fact un-approves the drafts built on it", () => {
    store().approveDraft(DRAFT_ID);

    store().correctFact("fact-cadastral-map-no", "Synthetic map", "Synthetic reason");

    expect(store().drafts.find((d) => d.id === DRAFT_ID)?.approvalState).not.toBe("approved");
  });
});

describe("assistant and profile", () => {
  it("recordAssistantAction audits the action against the answer", () => {
    store().recordAssistantAction("answer-synthetic", "copied");

    expect(lastEvent()).toMatchObject({
      action: "assistant.copied",
      targetType: "answer",
      targetId: "answer-synthetic",
      matterId: DEMO_MATTER_ID,
    });
  });

  it("updateProfile sets given fields, clears null ones, and leaves the rest", () => {
    store().updateProfile({ jurisdiction: "Synthetic division", phone: "000" });

    store().updateProfile({ phone: null });

    expect(store().profile).toMatchObject({
      jurisdiction: "Synthetic division",
      phone: "",
      id: DEMO_USER_ID,
    });
  });
});

describe("persisted-state migration (v3 → v4)", () => {
  const migrate = (payload: unknown, version: number) => {
    const fn = useDemoStore.persist.getOptions().migrate;
    if (!fn) throw new Error("the store must declare a migration");
    return fn(payload, version) as ReturnType<typeof store>;
  };

  it("an unreadable payload falls back to the seed", () => {
    expect(migrate(null, 1).matters).toEqual(seededMatters);
    expect(migrate("synthetic", 1).facts).toEqual(seededFacts);
  });

  it("a current payload is carried as it is", () => {
    const matters = [{ ...head(seededMatters), reference: "SYN/KEEP" }];

    expect(migrate({ matters }, 4).matters).toEqual(matters);
  });

  it("an old matter keeps its legacy type and gets only a provisional subtype", () => {
    const { subtypeId, familyId, subtypeDecisionStatus, legacyMatterType, ...legacy } =
      head(seededMatters);
    void [subtypeId, familyId, subtypeDecisionStatus, legacyMatterType];

    const matter = head(migrate({ matters: [{ ...legacy, type: "transfer" }] }, 3).matters);

    expect(matter).toMatchObject({
      type: "transfer",
      legacyMatterType: "transfer",
      subtypeDecisionStatus: "PROVISIONAL",
    });
  });

  it("an old matter with no type is kept, not guessed", () => {
    const { type, subtypeId, familyId, legacyMatterType, ...legacy } = head(seededMatters);
    void [type, subtypeId, familyId, legacyMatterType];

    const matter = head(migrate({ matters: [legacy] }, 1).matters);

    expect(matter).toMatchObject({ id: legacy.id, type: "other" });
    expect(matter.subtypeId).toBeUndefined();
  });

  it.each([
    ["uploaded", "STORED"],
    ["extracting", "PROCESSING"],
    ["ready-for-review", "PROCESSED"],
    ["failed", "PROCESSING_FAILED"],
    ["replaced", "SUPERSEDED"],
    ["QUARANTINED", "QUARANTINED"],
    ["synthetic-unknown", "UPLOAD_INITIATED"],
  ])("an old document in %s is carried to %s", (legacy, expected) => {
    const documents = [{ ...head(seededDocuments), processingState: legacy }];

    expect(head(migrate({ documents }, 3).documents).processingState).toBe(expected);
  });

  it("no record is dropped", () => {
    const migrated = migrate({ matters: seededMatters, documents: seededDocuments }, 1);

    expect(migrated.matters).toHaveLength(seededMatters.length);
    expect(migrated.documents).toHaveLength(seededDocuments.length);
  });
});
