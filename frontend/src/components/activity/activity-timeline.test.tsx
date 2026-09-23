// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import en from "@/lib/i18n/messages/en.json";
import { DEMO_MATTER_ID } from "@/lib/mocks";
import { useDemoStore } from "@/lib/store";
import { renderWithIntl } from "@/test/render";
import { ActivityTimeline } from "./activity-timeline";

const store = () => useDemoStore.getState();
const GENERIC = en.activity.actions.updated;

beforeEach(() => {
  store().resetDemo();
});

describe("ActivityTimeline", () => {
  it("shows the newest event first", () => {
    store().verifyFact("fact-district");

    renderWithIntl(<ActivityTimeline />);

    const items = screen.getAllByRole("listitem");
    expect(items[0]?.textContent).toContain(en.activity.actions.factVerified);
  });

  it("shows only the chosen matter's events", () => {
    const other = store().createMatter({ reference: "SYN/0002", regime: "rta", type: "transfer" });
    store().addDocument("synthetic.pdf", "other", other);

    renderWithIntl(<ActivityTimeline matterId={DEMO_MATTER_ID} />);

    expect(screen.queryByText(new RegExp(`doc-upload`))).toBeNull();
  });

  it("says so when a matter has no events", () => {
    renderWithIntl(<ActivityTimeline matterId="matter-synthetic-empty" />);

    expect(screen.getByText(en.activity.noEvents)).toBeTruthy();
  });

  it("marks this session's events apart from the historical ones", () => {
    store().verifyFact("fact-district");

    renderWithIntl(<ActivityTimeline />);

    const items = screen.getAllByRole("listitem");
    expect(items[0]?.textContent).toContain(en.activity.liveSession);
    expect(items.at(-1)?.textContent).toContain(en.activity.historical);
  });

  it("gives every action the store records a specific label, not a generic one", () => {
    // Drive every store action that appends an event.
    const doc = store().addDocument("synthetic.pdf");
    store().markProcessingNotConfigured(doc);
    store().replaceDocument(doc, "synthetic-2.pdf", "Synthetic rescan");
    store().verifyFact("fact-district");
    store().correctFact("fact-district", "Synthetic", "Synthetic reason");
    store().addManualFact("facts.manualValue", "Synthetic", "Synthetic reason");
    for (const action of ["resolved", "waived", "document-requested", "checklist-created"] as const) {
      store().resolveCheck("check-title-cert-0020", action, "Synthetic reason");
    }
    const workflow = store().workflows[0];
    const step = workflow?.steps[0];
    if (!workflow || !step) throw new Error("expected a seeded workflow step");
    store().completeStep(workflow.id, step.id, "Synthetic note");
    store().completeStep(workflow.id, step.id, undefined, "Synthetic override");
    const draft = store().drafts[0]?.id ?? "";
    store().saveDraftVersion(draft, { type: "doc", content: [] });
    store().restoreDraftVersion(draft, store().drafts[0]?.versions[0]?.id ?? "");
    store().approveDraft(draft);
    store().exportDraft(draft, "pdf");
    store().recordAssistantAction("answer-synthetic", "question-asked");
    store().createMatter({ reference: "SYN/0003", regime: "rta", type: "transfer" });

    renderWithIntl(<ActivityTimeline />);

    const generic = screen
      .getAllByRole("listitem")
      .filter((item) => item.querySelector(".font-medium")?.textContent === GENERIC);
    expect(generic).toEqual([]);
  });
});
