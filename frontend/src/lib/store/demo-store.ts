"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { auditEvents, checks, DEMO_MATTER_ID, DEMO_USER_ID, documents, drafts, facts, matters, workflows } from "@/lib/mocks";
import type { AuditEvent, Check, Draft, EditorDocument, Matter, MatterDocument, MatterType, ProcessingState, RegistrationRegime, VerifiedFact, Workflow } from "@/types";

const seed = () => ({ matters: structuredClone(matters), documents: structuredClone(documents), facts: structuredClone(facts), checks: structuredClone(checks), workflows: structuredClone(workflows), drafts: structuredClone(drafts), auditEvents: structuredClone(auditEvents) });

const deterministicTimestamp = (eventCount: number) => new Date(Date.UTC(2026, 6, 22, 10, eventCount, 0)).toISOString();
const eventId = (eventCount: number) => `audit-live-${String(eventCount + 1).padStart(3, "0")}`;

type CreateMatterInput = { reference: string; clientReference?: string; regime: RegistrationRegime; type: MatterType };

interface DemoState {
  matters: Matter[];
  documents: MatterDocument[];
  facts: VerifiedFact[];
  checks: Check[];
  workflows: Workflow[];
  drafts: Draft[];
  auditEvents: AuditEvent[];
  createMatter: (input: CreateMatterInput) => string;
  addDocument: (fileName: string, kind?: MatterDocument["kind"]) => string;
  setDocumentProcessingState: (documentId: string, processingState: ProcessingState, confidence?: number) => void;
  retryDocument: (documentId: string) => void;
  replaceDocument: (documentId: string, fileName: string, reason: string) => void;
  verifyFact: (factId: string) => void;
  correctFact: (factId: string, value: VerifiedFact["value"], reason: string) => void;
  addManualFact: (labelKey: string, value: VerifiedFact["value"], reason: string) => string;
  resolveCheck: (checkId: string, action: NonNullable<Check["resolution"]>["action"], reason: string) => void;
  completeStep: (workflowId: string, stepId: string, note?: string, overrideReason?: string) => void;
  createDraft: (matterId: string, templateId: string) => string | null;
  saveDraftVersion: (draftId: string, document: EditorDocument) => void;
  restoreDraftVersion: (draftId: string, versionId: string) => void;
  approveDraft: (draftId: string) => void;
  exportDraft: (draftId: string, format: "docx" | "pdf") => void;
  recordAssistantAction: (answerId: string, action: string) => void;
  resetDemo: () => void;
}

function appendEvent(state: DemoState, event: Omit<AuditEvent, "id" | "timestamp" | "actor">): AuditEvent[] {
  const count = state.auditEvents.length;
  return [...state.auditEvents, { ...event, id: eventId(count), actor: DEMO_USER_ID, timestamp: deterministicTimestamp(count) }];
}

export const useDemoStore = create<DemoState>()(persist((set, get) => ({
  ...seed(),
  // TODO(api): POST /api/matters
  createMatter: (input) => {
    const id = `matter-rta-${String(get().matters.length + 1).padStart(3, "0")}`;
    set((state) => {
      const timestamp = deterministicTimestamp(state.auditEvents.length);
      const matter: Matter = { id, ...input, parties: [], status: "open", activeFunction: "examination", progress: { examination: 0, drafting: 0, execution: 0, attestation: 0 }, ownerId: DEMO_USER_ID, createdAt: timestamp, updatedAt: timestamp };
      return { matters: [...state.matters, matter], auditEvents: appendEvent(state, { matterId: id, action: "matter.created", targetType: "matter", targetId: id, after: matter }) };
    });
    return id;
  },
  // TODO(api): POST /api/matters/{matterId}/documents
  addDocument: (fileName, kind = "other") => {
    const id = `doc-upload-${String(get().documents.length + 1).padStart(3, "0")}`;
    set((state) => {
      const document: MatterDocument = { id, matterId: DEMO_MATTER_ID, fileName, kind, language: "en", pageCount: 1, processingState: "uploaded", qualityProblems: [], versions: [], uploadedAt: deterministicTimestamp(state.auditEvents.length) };
      return { documents: [...state.documents, document], auditEvents: appendEvent(state, { matterId: DEMO_MATTER_ID, action: "document.uploaded", targetType: "document", targetId: id, after: document }) };
    });
    return id;
  },
  // TODO(api): PATCH /api/matters/{matterId}/documents/{documentId}/processing
  setDocumentProcessingState: (documentId, processingState, confidence) => set((state) => {
    const before = state.documents.find((document) => document.id === documentId);
    const updated = state.documents.map((document) => document.id === documentId ? { ...document, processingState, extractionConfidence: confidence ?? document.extractionConfidence } : document);
    return { documents: updated, auditEvents: appendEvent(state, { matterId: before?.matterId ?? DEMO_MATTER_ID, action: `document.${processingState}`, targetType: "document", targetId: documentId, before, after: updated.find((document) => document.id === documentId) }) };
  }),
  // TODO(api): POST /api/matters/{matterId}/documents/{documentId}/retry
  retryDocument: (documentId) => set((state) => ({ documents: state.documents.map((document) => document.id === documentId ? { ...document, processingState: "uploaded" } : document), auditEvents: appendEvent(state, { matterId: DEMO_MATTER_ID, action: "document.retry-requested", targetType: "document", targetId: documentId }) })),
  // TODO(api): POST /api/matters/{matterId}/documents/{documentId}/versions
  replaceDocument: (documentId, fileName, reason) => set((state) => {
    const document = state.documents.find((item) => item.id === documentId);
    const version = { id: `docver-live-${state.auditEvents.length + 1}`, documentId, fileName, replacedVersionId: document?.versions.at(-1)?.id, replacedBy: DEMO_USER_ID, reason, timestamp: deterministicTimestamp(state.auditEvents.length) };
    return { documents: state.documents.map((item) => item.id === documentId ? { ...item, fileName, processingState: "uploaded", versions: [...item.versions, version] } : item), auditEvents: appendEvent(state, { matterId: document?.matterId ?? DEMO_MATTER_ID, action: "document.replaced", targetType: "document", targetId: documentId, before: document, after: version }) };
  }),
  // TODO(api): POST /api/matters/{matterId}/facts/{factId}/verify
  verifyFact: (factId) => set((state) => {
    const before = state.facts.find((fact) => fact.id === factId);
    const reviewedAt = deterministicTimestamp(state.auditEvents.length);
    const updated = state.facts.map((fact) => fact.id === factId ? { ...fact, verificationState: "verified" as const, reviewerId: DEMO_USER_ID, reviewedAt } : fact);
    return { facts: updated, auditEvents: appendEvent(state, { matterId: before?.matterId ?? DEMO_MATTER_ID, action: "fact.verified", targetType: "fact", targetId: factId, before, after: updated.find((fact) => fact.id === factId) }) };
  }),
  // TODO(api): POST /api/matters/{matterId}/facts/{factId}/correct
  correctFact: (factId, value, reason) => set((state) => {
    const before = state.facts.find((fact) => fact.id === factId);
    const reviewedAt = deterministicTimestamp(state.auditEvents.length);
    const updated = state.facts.map((fact) => fact.id === factId ? { ...fact, value, verificationState: "corrected" as const, reviewerId: DEMO_USER_ID, reviewedAt, changes: [...fact.changes, { id: `change-live-${state.auditEvents.length + 1}`, before: fact.value, after: value, reason, actorId: DEMO_USER_ID, timestamp: reviewedAt }] } : fact);
    return { facts: updated, auditEvents: appendEvent(state, { matterId: before?.matterId ?? DEMO_MATTER_ID, action: "fact.corrected", targetType: "fact", targetId: factId, before, after: updated.find((fact) => fact.id === factId) }) };
  }),
  // TODO(api): POST /api/matters/{matterId}/facts
  addManualFact: (labelKey, value, reason) => {
    const id = `fact-manual-${String(get().facts.length + 1).padStart(3, "0")}`;
    set((state) => {
      const fact: VerifiedFact = { id, matterId: DEMO_MATTER_ID, key: id, labelKey, section: "manual", value, extractedValue: null, confidence: 1, verificationState: "unreviewed", changes: [], manualReason: reason };
      return { facts: [...state.facts, fact], auditEvents: appendEvent(state, { matterId: DEMO_MATTER_ID, action: "fact.added-manually", targetType: "fact", targetId: id, after: fact }) };
    });
    return id;
  },
  // TODO(api): POST /api/matters/{matterId}/checks/{checkId}/resolve
  resolveCheck: (checkId, action, reason) => set((state) => {
    const before = state.checks.find((check) => check.id === checkId);
    const resolution = { action, reason, actorId: DEMO_USER_ID, timestamp: deterministicTimestamp(state.auditEvents.length) };
    return { checks: state.checks.map((check) => check.id === checkId ? { ...check, status: "pass", resolution } : check), auditEvents: appendEvent(state, { matterId: before?.matterId ?? DEMO_MATTER_ID, action: `check.${action}`, targetType: "check", targetId: checkId, before, after: resolution }) };
  }),
  // TODO(api): POST /api/matters/{matterId}/workflows/{workflowId}/steps/{stepId}/complete
  completeStep: (workflowId, stepId, note, overrideReason) => set((state) => ({ workflows: state.workflows.map((workflow) => workflow.id === workflowId ? { ...workflow, steps: workflow.steps.map((step) => step.id === stepId ? { ...step, state: "complete", note, overrideReason } : step) } : workflow), auditEvents: appendEvent(state, { matterId: DEMO_MATTER_ID, action: overrideReason ? "workflow.step-overridden" : "workflow.step-completed", targetType: "workflow-step", targetId: stepId, after: { note, overrideReason } }) })),
  // TODO(api): POST /api/matters/{matterId}/drafts
  createDraft: (matterId, templateId) => {
    const eligible = get().facts.filter((fact) => fact.matterId === matterId && ["verified", "corrected"].includes(fact.verificationState));
    if (!eligible.some((fact) => fact.id === "fact-transferee") || !eligible.some((fact) => fact.id === "fact-extent")) return null;
    const id = `draft-live-${String(get().drafts.length + 1).padStart(3, "0")}`;
    set((state) => {
      const createdAt = deterministicTimestamp(state.auditEvents.length);
      const document: EditorDocument = { type: "doc", content: [{ type: "heading", attrs: { level: 1 }, content: [{ type: "text", text: "Form 8 — synthetic draft" }] }, { type: "paragraph", content: eligible.map((fact) => ({ type: "factChip" as const, attrs: { fact_id: fact.id, verification_state: fact.verificationState as "verified" | "corrected" } })) }] };
      const draft: Draft = { id, matterId, title: "Form 8 transfer — synthetic", templateId, approvalState: "working", activeVersionId: `${id}-v1`, versions: [{ id: `${id}-v1`, draftId: id, number: 1, hash: `syn${state.drafts.length + 1}001`, document, createdBy: DEMO_USER_ID, createdAt }] };
      return { drafts: [...state.drafts, draft], auditEvents: appendEvent(state, { matterId, action: "draft.created", targetType: "draft", targetId: id, after: draft }) };
    });
    return id;
  },
  // TODO(api): POST /api/matters/{matterId}/drafts/{draftId}/versions
  saveDraftVersion: (draftId, document) => set((state) => ({ drafts: state.drafts.map((draft) => {
    if (draft.id !== draftId) return draft;
    const number = draft.versions.length + 1;
    const id = `${draftId}-v${number}`;
    return { ...draft, activeVersionId: id, versions: [...draft.versions, { id, draftId, number, hash: `syn${number}e${state.auditEvents.length}`, document, createdBy: DEMO_USER_ID, createdAt: deterministicTimestamp(state.auditEvents.length) }] };
  }), auditEvents: appendEvent(state, { matterId: DEMO_MATTER_ID, action: "draft.version-created", targetType: "draft", targetId: draftId }) })),
  // TODO(api): POST /api/matters/{matterId}/drafts/{draftId}/restore
  restoreDraftVersion: (draftId, versionId) => set((state) => ({ drafts: state.drafts.map((draft) => {
    if (draft.id !== draftId) return draft;
    const source = draft.versions.find((version) => version.id === versionId);
    if (!source) return draft;
    const number = draft.versions.length + 1;
    const id = `${draftId}-v${number}`;
    return { ...draft, activeVersionId: id, approvalState: "working", versions: [...draft.versions, { ...source, id, number, hash: `restore${number}`, createdAt: deterministicTimestamp(state.auditEvents.length), restoredFromVersionId: source.id }] };
  }), auditEvents: appendEvent(state, { matterId: DEMO_MATTER_ID, action: "draft.version-restored", targetType: "draft", targetId: draftId, after: { versionId } }) })),
  // TODO(api): POST /api/matters/{matterId}/drafts/{draftId}/approve
  approveDraft: (draftId) => set((state) => ({ drafts: state.drafts.map((draft) => draft.id === draftId ? { ...draft, approvalState: "approved", approvedBy: DEMO_USER_ID, approvedAt: deterministicTimestamp(state.auditEvents.length) } : draft), auditEvents: appendEvent(state, { matterId: DEMO_MATTER_ID, action: "draft.approved", targetType: "draft", targetId: draftId }) })),
  // TODO(api): POST /api/matters/{matterId}/drafts/{draftId}/exports
  exportDraft: (draftId, format) => set((state) => ({ drafts: state.drafts.map((draft) => draft.id === draftId ? { ...draft, approvalState: "exported" } : draft), auditEvents: appendEvent(state, { matterId: DEMO_MATTER_ID, action: `draft.exported-${format}`, targetType: "draft", targetId: draftId, after: { format } }) })),
  // TODO(api): POST /api/assistant/actions
  recordAssistantAction: (answerId, action) => set((state) => ({ auditEvents: appendEvent(state, { matterId: DEMO_MATTER_ID, action: `assistant.${action}`, targetType: "answer", targetId: answerId }) })),
  // TODO(api): POST /api/demo/reset
  resetDemo: () => {
    const reset = seed();
    set({ ...reset, auditEvents: [...reset.auditEvents, { id: "audit-reset", matterId: DEMO_MATTER_ID, actor: DEMO_USER_ID, action: "demo.reset", targetType: "matter", targetId: DEMO_MATTER_ID, timestamp: deterministicTimestamp(reset.auditEvents.length) }] });
  }
}), { name: "draftly-m2-demo", storage: createJSONStorage(() => localStorage), version: 1 }));
