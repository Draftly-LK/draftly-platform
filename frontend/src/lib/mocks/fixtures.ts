import type {
  Authority,
  AuditEvent,
  Check,
  CrossCheck,
  Draft,
  FormTemplate,
  GroundedAnswer,
  Matter,
  MatterDocument,
  Obligation,
  Question,
  QuestionSet,
  User,
  VerifiedFact,
  Workflow,
} from "@/types";

export const FIXED_NOW = "2026-07-22T09:30:00.000Z";
export const DEMO_MATTER_ID = "matter-rta-001";
export const DEMO_USER_ID = "user-reviewer-001";

export const users: User[] = [
  {
    id: DEMO_USER_ID,
    displayName: "N. M. Silva (synthetic)",
    role: "approver",
    notaryRegistration: "SYN-NP-0042",
    jurisdiction: "Western Province (synthetic)",
    qualifications: "LL.B (Sri Lanka) LL.M (synthetic) M CL (synthetic)",
    professionalTitles: "Attorney-at-Law · Notary Public",
    addressLine1: "No. 12, Synthetic Avenue",
    addressLine2: "Colombo (synthetic)",
    phone: "0700000000",
  },
];

export const matters: Matter[] = [
  {
    id: DEMO_MATTER_ID,
    reference: "RTA-2026-SYN-014",
    clientReference: "CLIENT-SYN-104",
    regime: "rta",
    type: "transfer",
    parties: [
      {
        id: "party-001",
        role: "transferor",
        nameToken: "A. B. Perera (synthetic)",
        identityDocumentReference: "ID-SYN-4102",
      },
      {
        id: "party-002",
        role: "transferee",
        nameToken: "C. D. Fernando (synthetic)",
        identityDocumentReference: "ID-SYN-8831",
      },
    ],
    status: "in-review",
    activeFunction: "examination",
    progress: { examination: 42, drafting: 0, execution: 0, attestation: 0 },
    ownerId: DEMO_USER_ID,
    createdAt: "2026-07-17T04:10:00.000Z",
    updatedAt: FIXED_NOW,
  },
];

export const documents: MatterDocument[] = [
  {
    id: "doc-deed-001",
    matterId: DEMO_MATTER_ID,
    fileName: "deed-4821-synthetic.pdf",
    kind: "deed",
    language: "en",
    pageCount: 8,
    processingState: "ready-for-review",
    extractionConfidence: 0.94,
    qualityProblems: [],
    versions: [
      {
        id: "docver-001",
        documentId: "doc-deed-001",
        fileName: "deed-4821-synthetic.pdf",
        replacedBy: DEMO_USER_ID,
        reason: "Initial synthetic upload",
        timestamp: "2026-07-17T04:14:00.000Z",
      },
    ],
    uploadedAt: "2026-07-17T04:14:00.000Z",
  },
  {
    id: "doc-plan-001",
    matterId: DEMO_MATTER_ID,
    fileName: "plan-771-synthetic.pdf",
    kind: "survey-plan",
    language: "mixed",
    pageCount: 2,
    processingState: "ready-for-review",
    extractionConfidence: 0.77,
    qualityProblems: [{ code: "low-contrast", pages: [2] }],
    versions: [
      {
        id: "docver-002",
        documentId: "doc-plan-001",
        fileName: "plan-771-original-synthetic.pdf",
        replacedBy: DEMO_USER_ID,
        reason: "Initial synthetic upload",
        timestamp: "2026-07-17T04:15:00.000Z",
      },
      {
        id: "docver-003",
        documentId: "doc-plan-001",
        fileName: "plan-771-synthetic.pdf",
        replacedVersionId: "docver-002",
        replacedBy: DEMO_USER_ID,
        reason: "Clearer scan supplied (synthetic)",
        timestamp: "2026-07-18T05:20:00.000Z",
      },
    ],
    uploadedAt: "2026-07-17T04:15:00.000Z",
  },
  {
    id: "doc-id-001",
    matterId: DEMO_MATTER_ID,
    fileName: "identity-synthetic.pdf",
    kind: "identity",
    language: "en",
    pageCount: 1,
    processingState: "extracting",
    extractionConfidence: 0.61,
    qualityProblems: [{ code: "blur", pages: [1] }],
    versions: [],
    uploadedAt: "2026-07-22T09:28:00.000Z",
  },
  {
    id: "doc-assessment-001",
    matterId: DEMO_MATTER_ID,
    fileName: "assessment-synthetic.pdf",
    kind: "assessment",
    language: "si",
    pageCount: 1,
    processingState: "uploaded",
    qualityProblems: [],
    versions: [],
    uploadedAt: "2026-07-22T09:29:00.000Z",
  },
  {
    id: "doc-registry-001",
    matterId: DEMO_MATTER_ID,
    fileName: "registry-extract-synthetic.pdf",
    kind: "registry-extract",
    language: "en",
    pageCount: 3,
    processingState: "failed",
    qualityProblems: [{ code: "cropped", pages: [3] }],
    versions: [],
    uploadedAt: "2026-07-20T07:10:00.000Z",
  },
  {
    id: "doc-at-001",
    matterId: DEMO_MATTER_ID,
    fileName: "at-form-synthetic.pdf",
    kind: "at-form",
    language: "en",
    pageCount: 1,
    processingState: "replaced",
    qualityProblems: [],
    versions: [
      {
        id: "docver-at-001",
        documentId: "doc-at-001",
        fileName: "at-form-synthetic.pdf",
        replacedBy: DEMO_USER_ID,
        reason: "AT forms unsupported in M2",
        timestamp: "2026-07-19T03:00:00.000Z",
      },
    ],
    uploadedAt: "2026-07-19T03:00:00.000Z",
  },
];

const span = (documentId: string, page: number, snippet: string) => ({
  documentId,
  page,
  region: { x: 12, y: 18, width: 72, height: 8 },
  snippet,
});

export const facts: VerifiedFact[] = [
  {
    id: "fact-deed-no",
    matterId: DEMO_MATTER_ID,
    key: "deedNumber",
    labelKey: "facts.deedNumber",
    section: "instrument",
    value: "4821 (synthetic)",
    extractedValue: "4821 (synthetic)",
    evidence: span("doc-deed-001", 1, "Deed No. 4821 — synthetic evidence"),
    confidence: 0.97,
    verificationState: "verified",
    reviewerId: DEMO_USER_ID,
    reviewedAt: "2026-07-21T05:12:00.000Z",
    changes: [],
  },
  {
    id: "fact-transferor",
    matterId: DEMO_MATTER_ID,
    key: "transferor",
    labelKey: "facts.transferor",
    section: "parties",
    value: "A. B. Perera (synthetic)",
    extractedValue: "A. B. Pereira (synthetic)",
    evidence: span("doc-deed-001", 2, "A. B. Perera (synthetic)"),
    confidence: 0.83,
    verificationState: "corrected",
    reviewerId: DEMO_USER_ID,
    reviewedAt: "2026-07-21T05:16:00.000Z",
    changes: [
      {
        id: "change-001",
        before: "A. B. Pereira (synthetic)",
        after: "A. B. Perera (synthetic)",
        reason: "Matched synthetic identity document",
        actorId: DEMO_USER_ID,
        timestamp: "2026-07-21T05:16:00.000Z",
      },
    ],
  },
  {
    id: "fact-transferee",
    matterId: DEMO_MATTER_ID,
    key: "transferee",
    labelKey: "facts.transferee",
    section: "parties",
    value: "C. D. Fernando (synthetic)",
    extractedValue: "C. D. Fernando (synthetic)",
    evidence: span("doc-deed-001", 2, "C. D. Fernando (synthetic)"),
    confidence: 0.91,
    verificationState: "unreviewed",
    changes: [],
  },
  {
    id: "fact-extent",
    matterId: DEMO_MATTER_ID,
    key: "extent",
    labelKey: "facts.extent",
    section: "parcel",
    value: "0A 2R 14.5P (synthetic)",
    extractedValue: "0A 2R 14.5P (synthetic)",
    evidence: span("doc-deed-001", 6, "Extent: 0A 2R 14.5P — synthetic"),
    confidence: 0.72,
    verificationState: "conflict",
    changes: [],
    conflicts: [
      {
        value: "0A 2R 14.5P (synthetic)",
        evidence: span("doc-deed-001", 6, "Extent: 0A 2R 14.5P — synthetic"),
        confidence: 0.92,
      },
      {
        value: "0A 2R 12.0P (synthetic)",
        evidence: span("doc-plan-001", 1, "Extent: 0A 2R 12.0P — synthetic"),
        confidence: 0.89,
      },
    ],
  },
  {
    id: "fact-assessment",
    matterId: DEMO_MATTER_ID,
    key: "assessmentNumber",
    labelKey: "facts.assessmentNumber",
    section: "parcel",
    value: null,
    extractedValue: null,
    confidence: 0,
    verificationState: "blocked",
    changes: [],
  },
];

export const authority: Authority = {
  id: "authority-rta-syn",
  title: "RTA authority reference (synthetic summary)",
  reference: "SYN-RTA-REF-01",
  type: "statute",
  courtLevel: "not-applicable",
  weight: "binding",
  verified: true,
};

export const checks: Check[] = [
  {
    id: "check-identity",
    matterId: DEMO_MATTER_ID,
    category: "identity",
    descriptionKey: "checks.identityPass",
    status: "pass",
    affectedFactIds: ["fact-transferor"],
    evidence: [span("doc-id-001", 1, "Synthetic identity reference")],
    authority,
    suggestedResolutionKey: "checks.noAction",
  },
  {
    id: "check-plan",
    matterId: DEMO_MATTER_ID,
    category: "parcel",
    descriptionKey: "checks.extentConflict",
    status: "warning",
    affectedFactIds: ["fact-extent"],
    evidence: [span("doc-plan-001", 1, "Synthetic extent mismatch")],
    authority,
    suggestedResolutionKey: "checks.compareEvidence",
    ownerId: DEMO_USER_ID,
  },
  {
    id: "check-registry",
    matterId: DEMO_MATTER_ID,
    category: "missing-document",
    descriptionKey: "checks.registryMissing",
    status: "fail",
    affectedFactIds: [],
    evidence: [],
    authority,
    suggestedResolutionKey: "checks.requestDocument",
    ownerId: DEMO_USER_ID,
  },
  {
    id: "check-boundary",
    matterId: DEMO_MATTER_ID,
    category: "parcel",
    descriptionKey: "checks.boundaryReview",
    status: "needs-review",
    affectedFactIds: ["fact-extent"],
    evidence: [span("doc-deed-001", 6, "Synthetic boundary description")],
    authority,
    suggestedResolutionKey: "checks.reviewBoundary",
  },
];

export const crossChecks: CrossCheck[] = [
  {
    id: "cross-extent",
    matterId: DEMO_MATTER_ID,
    labelKey: "checks.extentTally",
    verdict: "mismatch",
    checkId: "check-plan",
    bindings: [
      {
        factId: "fact-extent",
        evidence: span("doc-deed-001", 6, "Deed extent — synthetic"),
      },
      {
        factId: "fact-extent",
        evidence: span("doc-plan-001", 1, "Plan extent — synthetic"),
      },
    ],
  },
];

export const workflows: Workflow[] = [
  {
    id: "workflow-exam-001",
    titleKey: "workflow.examinationTitle",
    regime: "rta",
    transactionTypes: ["transfer"],
    function: "examination",
    approvalState: "approved",
    language: "bilingual",
    ownerId: DEMO_USER_ID,
    version: "1.2",
    steps: [
      {
        id: "step-identity",
        workflowId: "workflow-exam-001",
        order: 1,
        titleKey: "workflow.identityTitle",
        objectiveKey: "workflow.identityObjective",
        state: "complete",
        mandatory: true,
        requiredFactIds: ["fact-transferor", "fact-transferee"],
        requiredDocumentIds: ["doc-id-001"],
        authority,
        sourceExcerpt: "PLACEHOLDER — legal wording pending lawyer",
        rules: [
          {
            id: "rule-id",
            labelKey: "workflow.identityRule",
            keywords: ["identity", "party"],
          },
        ],
      },
      {
        id: "step-title",
        workflowId: "workflow-exam-001",
        order: 2,
        titleKey: "workflow.titleTitle",
        objectiveKey: "workflow.titleObjective",
        state: "in-progress",
        mandatory: true,
        requiredFactIds: ["fact-deed-no", "fact-extent"],
        requiredDocumentIds: ["doc-deed-001", "doc-plan-001"],
        authority,
        sourceExcerpt: "PLACEHOLDER — legal wording pending lawyer",
        rules: [
          {
            id: "rule-title",
            labelKey: "workflow.titleRule",
            keywords: ["title", "extent"],
          },
        ],
      },
      {
        id: "step-encumbrance",
        workflowId: "workflow-exam-001",
        order: 3,
        titleKey: "workflow.encumbranceTitle",
        objectiveKey: "workflow.encumbranceObjective",
        state: "blocked",
        mandatory: true,
        requiredFactIds: [],
        requiredDocumentIds: ["doc-registry-001"],
        authority,
        sourceExcerpt: "PLACEHOLDER — legal wording pending lawyer",
        rules: [
          {
            id: "rule-enc",
            labelKey: "workflow.encumbranceRule",
            keywords: ["registry", "encumbrance"],
          },
        ],
      },
      {
        id: "step-decision",
        workflowId: "workflow-exam-001",
        order: 4,
        titleKey: "workflow.decisionTitle",
        objectiveKey: "workflow.decisionObjective",
        state: "not-started",
        mandatory: true,
        requiredFactIds: [],
        requiredDocumentIds: [],
        authority,
        sourceExcerpt: "PLACEHOLDER — legal wording pending lawyer",
        rules: [],
      },
    ],
  },
];

export const answers: GroundedAnswer[] = [
  {
    id: "answer-grounded",
    kind: "grounded",
    question:
      "Which evidence should be compared for the synthetic parcel extent?",
    corpusLimitKey: "assistant.corpusLimit",
    claims: [
      {
        id: "claim-001",
        text: "Compare the synthetic deed schedule with the synthetic survey plan before relying on the extent.",
        citations: [
          {
            id: "cite-001",
            authority,
            evidence: span("doc-deed-001", 6, "Synthetic deed schedule extent"),
          },
          {
            id: "cite-002",
            authority: {
              ...authority,
              id: "authority-gazette-syn",
              type: "gazette",
              reference: "SYN-GAZ-02",
              weight: "persuasive",
            },
            evidence: span("doc-plan-001", 1, "Synthetic survey plan extent"),
          },
        ],
      },
    ],
  },
  {
    id: "answer-insufficient",
    kind: "insufficient-authority",
    question:
      "Does an unsupported private arrangement override the registration record?",
    reasonKey: "assistant.insufficientReason",
    suggestedActionKey: "assistant.insufficientAction",
  },
];

export const templates: FormTemplate[] = [
  {
    id: "template-form8-001",
    formNumber: "Form 8",
    nameKey: "draft.form8Name",
    regime: "rta",
    transactionType: "transfer",
    approvalState: "approved",
    fields: [
      {
        id: "field-deed",
        labelKey: "facts.deedNumber",
        order: 1,
        required: true,
        factBinding: "fact-deed-no",
      },
      {
        id: "field-transferor",
        labelKey: "facts.transferor",
        order: 2,
        required: true,
        factBinding: "fact-transferor",
      },
      {
        id: "field-transferee",
        labelKey: "facts.transferee",
        order: 3,
        required: true,
        factBinding: "fact-transferee",
      },
      {
        id: "field-extent",
        labelKey: "facts.extent",
        order: 4,
        required: true,
        factBinding: "fact-extent",
      },
    ],
    blocks: [
      {
        id: "block-prescribed-001",
        order: 1,
        kind: "locked-prescribed",
        placeholderText: "PLACEHOLDER — legal wording pending lawyer",
      },
      {
        id: "block-particulars-001",
        order: 2,
        kind: "editable",
        placeholderText: "PLACEHOLDER — legal wording pending lawyer",
      },
    ],
  },
];

export const drafts: Draft[] = [
  {
    id: "draft-form8-001",
    matterId: DEMO_MATTER_ID,
    title: "Form 8 transfer — synthetic",
    templateId: "template-form8-001",
    approvalState: "in-review",
    activeVersionId: "draftver-002",
    versions: [
      {
        id: "draftver-001",
        draftId: "draft-form8-001",
        number: 1,
        hash: "8fa2c1",
        createdBy: DEMO_USER_ID,
        createdAt: "2026-07-21T06:00:00.000Z",
        document: {
          type: "doc",
          content: [
            {
              type: "heading",
              attrs: { level: 1 },
              content: [{ type: "text", text: "Form 8 — synthetic draft" }],
            },
            {
              type: "lockedBlock",
              attrs: { template_block_id: "block-prescribed-001" },
              content: [
                {
                  type: "paragraph",
                  content: [
                    {
                      type: "text",
                      text: "PLACEHOLDER — legal wording pending lawyer",
                    },
                  ],
                },
              ],
            },
          ],
        },
      },
      {
        id: "draftver-002",
        draftId: "draft-form8-001",
        number: 2,
        hash: "c41e09",
        createdBy: DEMO_USER_ID,
        createdAt: "2026-07-22T07:00:00.000Z",
        document: {
          type: "doc",
          content: [
            {
              type: "heading",
              attrs: { level: 1 },
              content: [{ type: "text", text: "Form 8 — synthetic draft" }],
            },
            {
              type: "lockedBlock",
              attrs: { template_block_id: "block-prescribed-001" },
              content: [
                {
                  type: "paragraph",
                  content: [
                    {
                      type: "text",
                      text: "PLACEHOLDER — legal wording pending lawyer",
                    },
                  ],
                },
              ],
            },
            {
              type: "paragraph",
              content: [
                { type: "text", text: "Verified deed: " },
                {
                  type: "factChip",
                  attrs: {
                    fact_id: "fact-deed-no",
                    verification_state: "verified",
                  },
                },
              ],
            },
          ],
        },
      },
    ],
  },
];

export const obligations: Obligation[] = [
  {
    id: "obligation-monthly",
    matterId: DEMO_MATTER_ID,
    labelKey: "obligations.monthlyList",
    dueDate: "2026-07-31",
    status: "upcoming",
  },
  {
    id: "obligation-license",
    matterId: DEMO_MATTER_ID,
    labelKey: "obligations.licenseRenewal",
    dueDate: "2026-08-15",
    status: "upcoming",
  },
  {
    id: "obligation-review",
    matterId: DEMO_MATTER_ID,
    labelKey: "obligations.lawyerReview",
    dueDate: "2026-07-24",
    status: "due",
  },
];

export const questions: Question[] = [
  {
    id: "question-001",
    prompt: "Which synthetic records should tally before drafting?",
    scope: "matter",
    language: "en",
    frequentlyWrong: true,
  },
];
export const questionSets: QuestionSet[] = [
  {
    id: "qset-001",
    titleKey: "library.titleQuestions",
    descriptionKey: "library.questionSetDescription",
    questionIds: ["question-001"],
    approvalState: "approved",
    ownerId: DEMO_USER_ID,
  },
];

export const auditEvents: AuditEvent[] = [
  {
    id: "audit-001",
    matterId: DEMO_MATTER_ID,
    actor: DEMO_USER_ID,
    action: "matter.created",
    targetType: "matter",
    targetId: DEMO_MATTER_ID,
    timestamp: "2026-07-17T04:10:00.000Z",
  },
  {
    id: "audit-002",
    matterId: DEMO_MATTER_ID,
    actor: DEMO_USER_ID,
    action: "document.uploaded",
    targetType: "document",
    targetId: "doc-deed-001",
    timestamp: "2026-07-17T04:14:00.000Z",
  },
  {
    id: "audit-003",
    matterId: DEMO_MATTER_ID,
    actor: DEMO_USER_ID,
    action: "fact.corrected",
    targetType: "fact",
    targetId: "fact-transferor",
    timestamp: "2026-07-21T05:16:00.000Z",
  },
];
