"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import {
  auditEvents,
  checks,
  DEMO_MATTER_ID,
  DEMO_USER_ID,
  documents,
  drafts,
  facts,
  matters,
  templates,
  workflows,
} from "@/lib/mocks";
import { EDITABLE_PROFILE_FIELDS, type ProfileFieldPatch } from "@/lib/profile/profile-fields";
import { migrateLegacyMatterType } from "@/lib/rta/taxonomy";
import { buildTemplateDocument } from "@/lib/templates/build-document";
import { deriveTemplateReadiness } from "@/lib/templates/readiness";
import type {
  AuditEvent,
  Check,
  Draft,
  EditorDocument,
  LegacyProcessingState,
  Matter,
  MatterDocument,
  MatterType,
  RegistrationRegime,
  SourceFileState,
  User,
  VerifiedFact,
  Workflow,
} from "@/types";

const seedProfile = (): User => ({
  id: DEMO_USER_ID,
  // Name/email/photo come from Clerk when signed in — not seeded here.
  displayName: "",
  role: "approver",
  notaryRegistration: "",
  jurisdiction: "",
  qualifications: "",
  professionalTitles: "",
  addressLine1: "",
  addressLine2: "",
  phone: "",
});

const seed = () => ({
  matters: structuredClone(matters),
  documents: structuredClone(documents),
  facts: structuredClone(facts),
  checks: structuredClone(checks),
  workflows: structuredClone(workflows),
  drafts: structuredClone(drafts),
  auditEvents: structuredClone(auditEvents),
  profile: seedProfile(),
});

/**
 * Deterministic stand-in for a real content digest. It is NOT a SHA-256 of the
 * bytes — the browser never sees the server's stored object. The server
 * computes the real digest at quarantine (§6.2); this only keeps the demo
 * fixture-stable and is labelled synthetic wherever it is shown.
 */
const syntheticDigest = (seedText: string): string => {
  let hash = 0x811c9dc5;
  for (let index = 0; index < seedText.length; index += 1) {
    hash ^= seedText.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return `syn-sha256-${hash.toString(16).padStart(8, "0")}`;
};

const deterministicTimestamp = (eventCount: number) =>
  new Date(Date.UTC(2026, 6, 22, 10, eventCount, 0)).toISOString();
const eventId = (eventCount: number) =>
  `audit-live-${String(eventCount + 1).padStart(3, "0")}`;

type CreateMatterInput = {
  reference: string;
  clientReference?: string;
  regime: RegistrationRegime;
  type: MatterType;
};

/**
 * Profile fields editable on the profile screen (not Clerk-owned identity).
 * Derived from `EDITABLE_PROFILE_FIELDS` — a single source of truth shared
 * with the wire contract, rather than a third hand-maintained field list.
 */
export type EditableProfilePatch = ProfileFieldPatch;

interface DemoState {
  matters: Matter[];
  documents: MatterDocument[];
  facts: VerifiedFact[];
  checks: Check[];
  workflows: Workflow[];
  drafts: Draft[];
  auditEvents: AuditEvent[];
  profile: User;
  createMatter: (input: CreateMatterInput) => string;
  addDocument: (
    fileName: string,
    kind?: MatterDocument["kind"],
    matterId?: string,
  ) => string;
  /**
   * Record that a processing run could not be performed because no extraction
   * provider is configured in this build (§10.2 `PROCESSING_FAILED` with a
   * recoverable reason, §6.2).
   *
   * This is the only processing outcome the client may write. Nothing in the
   * frontend may move a source file to `PROCESSED`: only a server-side
   * processing run produces derivatives, and there is deliberately no
   * client-side path to that state.
   */
  markProcessingNotConfigured: (sourceFileId: string) => void;
  replaceDocument: (
    documentId: string,
    fileName: string,
    reason: string,
  ) => void;
  verifyFact: (factId: string) => void;
  correctFact: (
    factId: string,
    value: VerifiedFact["value"],
    reason: string,
  ) => void;
  addManualFact: (
    labelKey: string,
    value: VerifiedFact["value"],
    reason: string,
    matterId?: string,
  ) => string;
  resolveCheck: (
    checkId: string,
    action: NonNullable<Check["resolution"]>["action"],
    reason: string,
  ) => void;
  completeStep: (
    workflowId: string,
    stepId: string,
    note?: string,
    overrideReason?: string,
    matterId?: string,
  ) => void;
  createDraft: (
    matterId: string,
    templateId: string,
    labels?: Record<string, string>,
  ) => string | null;
  saveDraftVersion: (draftId: string, document: EditorDocument) => void;
  restoreDraftVersion: (draftId: string, versionId: string) => void;
  approveDraft: (draftId: string) => void;
  exportDraft: (draftId: string, format: "docx" | "pdf") => void;
  recordAssistantAction: (
    answerId: string,
    action: string,
    matterId?: string,
  ) => void;
  /** Local-only: the profile screen never sends this patch to the backend
   * on the demo path (there is no backend to send it to). */
  updateProfile: (patch: EditableProfilePatch) => void;
  resetDemo: () => void;
}

function appendEvent(
  state: DemoState,
  event: Omit<AuditEvent, "id" | "timestamp" | "actor">,
): AuditEvent[] {
  const count = state.auditEvents.length;
  return [
    ...state.auditEvents,
    {
      ...event,
      id: eventId(count),
      actor: DEMO_USER_ID,
      timestamp: deterministicTimestamp(count),
    },
  ];
}

/** Retired M2 processing vocabulary mapped onto §10.2 source-file states. */
const LEGACY_SOURCE_FILE_STATE: Record<LegacyProcessingState, SourceFileState> = {
  uploaded: "STORED",
  extracting: "PROCESSING",
  "ready-for-review": "PROCESSED",
  failed: "PROCESSING_FAILED",
  replaced: "SUPERSEDED",
};

const SOURCE_FILE_STATES: readonly SourceFileState[] = [
  "UPLOAD_INITIATED",
  "QUARANTINED",
  "VALIDATED",
  "STORED",
  "PROCESSING",
  "PROCESSED",
  "PROCESSING_FAILED",
  "REJECTED",
  "SUPERSEDED",
];

const isSourceFileState = (value: string): value is SourceFileState =>
  (SOURCE_FILE_STATES as readonly string[]).includes(value);

type SeededState = ReturnType<typeof seed>;
type PersistedMatter = Omit<Matter, "type"> & { type?: MatterType };
type PersistedDocument = Omit<MatterDocument, "processingState"> & {
  processingState?: string;
};
type PersistedState = Omit<Partial<SeededState>, "matters" | "documents"> & {
  matters?: PersistedMatter[];
  documents?: PersistedDocument[];
};

/**
 * Carry a persisted matter onto the RTA taxonomy (§3.6). The legacy value is
 * preserved, the derived subtype is always PROVISIONAL, and an unmapped legacy
 * value keeps the record with `subtypeId` left undefined rather than guessing.
 */
function migratePersistedMatter(matter: PersistedMatter): Matter {
  const legacyMatterType = matter.legacyMatterType ?? matter.type;
  const migrated =
    legacyMatterType === undefined ? null : migrateLegacyMatterType(legacyMatterType);
  return {
    ...matter,
    type: matter.type ?? "other",
    legacyMatterType,
    subtypeId: matter.subtypeId ?? migrated?.subtypeId,
    familyId: matter.familyId ?? migrated?.familyId,
    subtypeDecisionStatus: matter.subtypeDecisionStatus ?? "PROVISIONAL",
  };
}

function migratePersistedDocument(document: PersistedDocument): MatterDocument {
  const legacy = document.processingState;
  const processingState: SourceFileState =
    legacy !== undefined && legacy in LEGACY_SOURCE_FILE_STATE
      ? LEGACY_SOURCE_FILE_STATE[legacy as LegacyProcessingState]
      : legacy !== undefined && isSourceFileState(legacy)
        ? legacy
        : // Unrecognised legacy value: keep the record and assert the least we
          // can still defend — bytes were received, nothing more.
          "UPLOAD_INITIATED";
  return { ...document, processingState };
}

/**
 * Persist migration v3 → v4. Legacy records stay readable; nothing is dropped
 * and no state is invented. Only fields the new vocabulary needs are added.
 */
function migrateDemoState(persisted: unknown, version: number): DemoState {
  const base = seed();
  // zustand shallow-merges this over the live store, so returning the data
  // slice (without the action closures) is the intended shape. The cast is the
  // narrowest way to say that to TypeScript.
  const asState = (value: SeededState): DemoState => value as unknown as DemoState;
  if (typeof persisted !== "object" || persisted === null) return asState(base);
  const state = persisted as PersistedState;
  const carried: SeededState = { ...base, ...(state as Partial<SeededState>) };
  if (version >= 4) return asState(carried);
  return asState({
    ...carried,
    matters: (state.matters ?? base.matters).map(migratePersistedMatter),
    documents: (state.documents ?? base.documents).map(migratePersistedDocument),
  });
}

export const useDemoStore = create<DemoState>()(
  persist(
    (set, get) => ({
      ...seed(),
      // TODO(api): POST /api/matters
      createMatter: (input) => {
        const id = `matter-rta-${String(get().matters.length + 1).padStart(3, "0")}`;
        set((state) => {
          const timestamp = deterministicTimestamp(state.auditEvents.length);
          const sourceFacts = state.facts.filter(
            (fact) => fact.matterId === DEMO_MATTER_ID,
          );
          const factIds = new Map(
            sourceFacts.map((fact) => [fact.id, `${id}-${fact.id}`]),
          );
          const initializedFacts = sourceFacts.map((fact) => ({
            ...structuredClone(fact),
            id: factIds.get(fact.id) ?? `${id}-${fact.id}`,
            matterId: id,
          }));
          const initializedChecks = state.checks
            .filter((check) => check.matterId === DEMO_MATTER_ID)
            .map((check) => ({
              ...structuredClone(check),
              id: `${id}-${check.id}`,
              matterId: id,
              affectedFactIds: check.affectedFactIds.map(
                (factId) => factIds.get(factId) ?? factId,
              ),
            }));
          const matter: Matter = {
            id,
            ...input,
            parties: [],
            status: "open",
            activeFunction: "examination",
            progress: {
              examination: 0,
              drafting: 0,
              execution: 0,
              attestation: 0,
            },
            ownerId: DEMO_USER_ID,
            createdAt: timestamp,
            updatedAt: timestamp,
          };
          return {
            matters: [...state.matters, matter],
            facts: [...state.facts, ...initializedFacts],
            checks: [...state.checks, ...initializedChecks],
            auditEvents: appendEvent(state, {
              matterId: id,
              action: "matter.created",
              targetType: "matter",
              targetId: id,
              after: matter,
            }),
          };
        });
        return id;
      },
      // TODO(api): POST /api/v1/matters/{matterId}/source-files
      addDocument: (fileName, kind = "other", matterId = DEMO_MATTER_ID) => {
        const id = `doc-upload-${String(get().documents.length + 1).padStart(3, "0")}`;
        set((state) => {
          const document: MatterDocument = {
            id,
            matterId,
            fileName,
            kind,
            language: "en",
            pageCount: 1,
            // The bytes are held locally only; the demo build has no storage
            // service, so the row stops at STORED and never claims more.
            processingState: "STORED",
            qualityProblems: [],
            versions: [],
            uploadedAt: deterministicTimestamp(state.auditEvents.length),
            mediaType: "application/pdf",
            byteLength: 0,
            sha256: syntheticDigest(`${matterId}:${id}:${fileName}`),
            storageObjectVersion: "synthetic-v1",
            uploadActorId: DEMO_USER_ID,
            retentionClass: "MATTER_EVIDENCE",
            classStatus: "UNIDENTIFIED",
            versionRelationship: "CURRENT",
            physicalOriginal: "UNKNOWN",
          };
          return {
            documents: [...state.documents, document],
            auditEvents: appendEvent(state, {
              matterId,
              action: "document.uploaded",
              targetType: "document",
              targetId: id,
              after: document,
            }),
          };
        });
        return id;
      },
      // TODO(api): POST /api/v1/source-files/{id}/process
      markProcessingNotConfigured: (sourceFileId) =>
        set((state) => {
          const before = state.documents.find(
            (document) => document.id === sourceFileId,
          );
          const updated = state.documents.map((document) =>
            document.id === sourceFileId
              ? {
                  ...document,
                  processingState: "PROCESSING_FAILED" as const,
                  failureReason: "NOT_CONFIGURED" as const,
                  failureExplanationKey: "documents.failure.notConfigured",
                }
              : document,
          );
          return {
            documents: updated,
            auditEvents: appendEvent(state, {
              matterId: before?.matterId ?? DEMO_MATTER_ID,
              action: "source-file.processing-not-configured",
              targetType: "document",
              targetId: sourceFileId,
              before,
              after: updated.find((document) => document.id === sourceFileId),
            }),
          };
        }),
      // TODO(api): POST /api/v1/matters/{matterId}/source-files
      replaceDocument: (documentId, fileName, reason) =>
        set((state) => {
          const document = state.documents.find(
            (item) => item.id === documentId,
          );
          const version = {
            id: `docver-live-${state.auditEvents.length + 1}`,
            documentId,
            fileName,
            replacedVersionId: document?.versions.at(-1)?.id,
            replacedBy: DEMO_USER_ID,
            reason,
            timestamp: deterministicTimestamp(state.auditEvents.length),
          };
          return {
            documents: state.documents.map((item) =>
              item.id === documentId
                ? {
                    ...item,
                    fileName,
                    // Replacement bytes are a new source: stored, unprocessed,
                    // and carrying none of the previous run's failure state.
                    processingState: "STORED" as const,
                    sha256: syntheticDigest(`${item.id}:${fileName}:${version.id}`),
                    failureReason: undefined,
                    failureExplanationKey: undefined,
                    versions: [...item.versions, version],
                  }
                : item,
            ),
            auditEvents: appendEvent(state, {
              matterId: document?.matterId ?? DEMO_MATTER_ID,
              action: "document.replaced",
              targetType: "document",
              targetId: documentId,
              before: document,
              after: version,
            }),
          };
        }),
      // TODO(api): POST /api/matters/{matterId}/facts/{factId}/verify
      verifyFact: (factId) =>
        set((state) => {
          const before = state.facts.find((fact) => fact.id === factId);
          const reviewedAt = deterministicTimestamp(state.auditEvents.length);
          const updated = state.facts.map((fact) =>
            fact.id === factId
              ? {
                  ...fact,
                  verificationState: "verified" as const,
                  reviewerId: DEMO_USER_ID,
                  reviewedAt,
                }
              : fact,
          );
          return {
            facts: updated,
            auditEvents: appendEvent(state, {
              matterId: before?.matterId ?? DEMO_MATTER_ID,
              action: "fact.verified",
              targetType: "fact",
              targetId: factId,
              before,
              after: updated.find((fact) => fact.id === factId),
            }),
          };
        }),
      // TODO(api): POST /api/matters/{matterId}/facts/{factId}/correct
      correctFact: (factId, value, reason) =>
        set((state) => {
          const before = state.facts.find((fact) => fact.id === factId);
          const reviewedAt = deterministicTimestamp(state.auditEvents.length);
          const updated = state.facts.map((fact) =>
            fact.id === factId
              ? {
                  ...fact,
                  value,
                  verificationState: "corrected" as const,
                  reviewerId: DEMO_USER_ID,
                  reviewedAt,
                  changes: [
                    ...fact.changes,
                    {
                      id: `change-live-${state.auditEvents.length + 1}`,
                      before: fact.value,
                      after: value,
                      reason,
                      actorId: DEMO_USER_ID,
                      timestamp: reviewedAt,
                    },
                  ],
                }
              : fact,
          );
          return {
            facts: updated,
            auditEvents: appendEvent(state, {
              matterId: before?.matterId ?? DEMO_MATTER_ID,
              action: "fact.corrected",
              targetType: "fact",
              targetId: factId,
              before,
              after: updated.find((fact) => fact.id === factId),
            }),
          };
        }),
      // TODO(api): POST /api/matters/{matterId}/facts
      addManualFact: (labelKey, value, reason, matterId = DEMO_MATTER_ID) => {
        const id = `fact-manual-${String(get().facts.length + 1).padStart(3, "0")}`;
        set((state) => {
          const fact: VerifiedFact = {
            id,
            matterId,
            key: id,
            labelKey,
            section: "manual",
            value,
            extractedValue: null,
            confidence: 1,
            verificationState: "unreviewed",
            changes: [],
            manualReason: reason,
          };
          return {
            facts: [...state.facts, fact],
            auditEvents: appendEvent(state, {
              matterId,
              action: "fact.added-manually",
              targetType: "fact",
              targetId: id,
              after: fact,
            }),
          };
        });
        return id;
      },
      // TODO(api): POST /api/matters/{matterId}/checks/{checkId}/resolve
      resolveCheck: (checkId, action, reason) =>
        set((state) => {
          const before = state.checks.find((check) => check.id === checkId);
          const resolution = {
            action,
            reason,
            actorId: DEMO_USER_ID,
            timestamp: deterministicTimestamp(state.auditEvents.length),
          };
          return {
            checks: state.checks.map((check) =>
              check.id === checkId
                ? { ...check, status: "pass", resolution }
                : check,
            ),
            auditEvents: appendEvent(state, {
              matterId: before?.matterId ?? DEMO_MATTER_ID,
              action: `check.${action}`,
              targetType: "check",
              targetId: checkId,
              before,
              after: resolution,
            }),
          };
        }),
      // TODO(api): POST /api/matters/{matterId}/workflows/{workflowId}/steps/{stepId}/complete
      completeStep: (
        workflowId,
        stepId,
        note,
        overrideReason,
        matterId = DEMO_MATTER_ID,
      ) =>
        set((state) => ({
          workflows: state.workflows.map((workflow) =>
            workflow.id === workflowId
              ? {
                  ...workflow,
                  steps: workflow.steps.map((step) =>
                    step.id === stepId
                      ? { ...step, state: "complete", note, overrideReason }
                      : step,
                  ),
                }
              : workflow,
          ),
          auditEvents: appendEvent(state, {
            matterId,
            action: overrideReason
              ? "workflow.step-overridden"
              : "workflow.step-completed",
            targetType: "workflow-step",
            targetId: stepId,
            after: { note, overrideReason },
          }),
        })),
      // TODO(api): POST /api/matters/{matterId}/drafts
      createDraft: (matterId, templateId, labels = {}) => {
        const template = templates.find((entry) => entry.id === templateId);
        if (!template) return null;
        const matterFacts = get().facts.filter((fact) => fact.matterId === matterId);
        // The form itself decides what it needs; the same derivation drives the
        // pre-flight checklist, so the gate can never disagree with the UI.
        if (!deriveTemplateReadiness(template, matterFacts).canGenerate) return null;
        const id = `draft-live-${String(get().drafts.length + 1).padStart(3, "0")}`;
        set((state) => {
          const createdAt = deterministicTimestamp(state.auditEvents.length);
          const document: EditorDocument = buildTemplateDocument(
            template,
            matterFacts,
            labels,
          );
          const draft: Draft = {
            id,
            matterId,
            title: `${template.formNumber} transfer`,
            templateId,
            approvalState: "working",
            activeVersionId: `${id}-v1`,
            versions: [
              {
                id: `${id}-v1`,
                draftId: id,
                number: 1,
                hash: `syn${state.drafts.length + 1}001`,
                document,
                createdBy: DEMO_USER_ID,
                createdAt,
              },
            ],
          };
          return {
            drafts: [...state.drafts, draft],
            auditEvents: appendEvent(state, {
              matterId,
              action: "draft.created",
              targetType: "draft",
              targetId: id,
              after: draft,
            }),
          };
        });
        return id;
      },
      // TODO(api): POST /api/matters/{matterId}/drafts/{draftId}/versions
      saveDraftVersion: (draftId, document) =>
        set((state) => ({
          drafts: state.drafts.map((draft) => {
            if (draft.id !== draftId) return draft;
            const number = draft.versions.length + 1;
            const id = `${draftId}-v${number}`;
            return {
              ...draft,
              activeVersionId: id,
              versions: [
                ...draft.versions,
                {
                  id,
                  draftId,
                  number,
                  hash: `syn${number}e${state.auditEvents.length}`,
                  document,
                  createdBy: DEMO_USER_ID,
                  createdAt: deterministicTimestamp(state.auditEvents.length),
                },
              ],
            };
          }),
          auditEvents: appendEvent(state, {
            matterId:
              state.drafts.find((draft) => draft.id === draftId)?.matterId ??
              DEMO_MATTER_ID,
            action: "draft.version-created",
            targetType: "draft",
            targetId: draftId,
          }),
        })),
      // TODO(api): POST /api/matters/{matterId}/drafts/{draftId}/restore
      restoreDraftVersion: (draftId, versionId) =>
        set((state) => ({
          drafts: state.drafts.map((draft) => {
            if (draft.id !== draftId) return draft;
            const source = draft.versions.find(
              (version) => version.id === versionId,
            );
            if (!source) return draft;
            const number = draft.versions.length + 1;
            const id = `${draftId}-v${number}`;
            return {
              ...draft,
              activeVersionId: id,
              approvalState: "working",
              versions: [
                ...draft.versions,
                {
                  ...source,
                  id,
                  number,
                  hash: `restore${number}`,
                  createdAt: deterministicTimestamp(state.auditEvents.length),
                  restoredFromVersionId: source.id,
                },
              ],
            };
          }),
          auditEvents: appendEvent(state, {
            matterId:
              state.drafts.find((draft) => draft.id === draftId)?.matterId ??
              DEMO_MATTER_ID,
            action: "draft.version-restored",
            targetType: "draft",
            targetId: draftId,
            after: { versionId },
          }),
        })),
      // TODO(api): POST /api/matters/{matterId}/drafts/{draftId}/approve
      approveDraft: (draftId) =>
        set((state) => ({
          drafts: state.drafts.map((draft) =>
            draft.id === draftId
              ? {
                  ...draft,
                  approvalState: "approved",
                  approvedBy: DEMO_USER_ID,
                  approvedAt: deterministicTimestamp(state.auditEvents.length),
                }
              : draft,
          ),
          auditEvents: appendEvent(state, {
            matterId:
              state.drafts.find((draft) => draft.id === draftId)?.matterId ??
              DEMO_MATTER_ID,
            action: "draft.approved",
            targetType: "draft",
            targetId: draftId,
          }),
        })),
      // TODO(api): POST /api/matters/{matterId}/drafts/{draftId}/exports
      exportDraft: (draftId, format) =>
        set((state) => ({
          drafts: state.drafts.map((draft) =>
            draft.id === draftId
              ? { ...draft, approvalState: "exported" }
              : draft,
          ),
          auditEvents: appendEvent(state, {
            matterId:
              state.drafts.find((draft) => draft.id === draftId)?.matterId ??
              DEMO_MATTER_ID,
            action: `draft.exported-${format}`,
            targetType: "draft",
            targetId: draftId,
            after: { format },
          }),
        })),
      // TODO(api): POST /api/assistant/actions
      recordAssistantAction: (answerId, action, matterId = DEMO_MATTER_ID) =>
        set((state) => ({
          auditEvents: appendEvent(state, {
            matterId,
            action: `assistant.${action}`,
            targetType: "answer",
            targetId: answerId,
          }),
        })),
      updateProfile: (patch) => {
        set((state) => {
          const profile = { ...state.profile };
          // `null` clears a field back to "" (this store's empty-string
          // representation of "unset"); `undefined` (an omitted key) leaves
          // the field untouched, mirroring the backend's `exclude_unset`.
          for (const key of EDITABLE_PROFILE_FIELDS) {
            const value = patch[key];
            if (value !== undefined) profile[key] = value ?? "";
          }
          return { profile };
        });
      },
      // TODO(api): POST /api/demo/reset
      resetDemo: () => {
        const reset = seed();
        set({
          ...reset,
          auditEvents: [
            ...reset.auditEvents,
            {
              id: "audit-reset",
              matterId: DEMO_MATTER_ID,
              actor: DEMO_USER_ID,
              action: "demo.reset",
              targetType: "matter",
              targetId: DEMO_MATTER_ID,
              timestamp: deterministicTimestamp(reset.auditEvents.length),
            },
          ],
        });
      },
    }),
    {
      name: "draftly-m2-demo",
      storage: createJSONStorage(() => localStorage),
      version: 4,
      migrate: migrateDemoState,
    },
  ),
);
