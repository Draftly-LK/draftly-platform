import type { RegistrationRegime } from "./matter";

export type TemplateId = string;
export type DraftApprovalState = "working" | "in-review" | "approved" | "exported";
export interface EditorTextNode { type: "text"; text: string; marks?: Array<{ type: string }> }
export interface EditorFactChipNode { type: "factChip"; attrs: { fact_id: string; verification_state: "verified" | "corrected" } }
export interface EditorParagraphNode { type: "paragraph"; content?: Array<EditorTextNode | EditorFactChipNode> }
export interface EditorHeadingNode { type: "heading"; attrs: { level: 1 | 2 | 3 }; content?: EditorTextNode[] }
export interface EditorLockedNode { type: "lockedBlock"; attrs: { template_block_id: string }; content?: EditorParagraphNode[] }
export interface EditorDocument { type: "doc"; content: Array<EditorParagraphNode | EditorHeadingNode | EditorLockedNode> }

export interface DraftVersion { id: string; draftId: string; number: number; hash: string; document: EditorDocument; createdBy: string; createdAt: string; restoredFromVersionId?: string }
export interface Draft { id: string; matterId: string; title: string; templateId: TemplateId; approvalState: DraftApprovalState; versions: DraftVersion[]; activeVersionId: string; approvedBy?: string; approvedAt?: string }
export interface FormTemplateField { id: string; labelKey: string; order: number; required: boolean; factBinding?: string }
export interface FormTemplateBlock { id: string; order: number; kind: "locked-prescribed" | "editable"; placeholderText: string }
export interface FormTemplate { id: TemplateId; formNumber: string; nameKey: string; regime: RegistrationRegime; transactionType: string; approvalState: "draft" | "approved" | "retired"; fields: FormTemplateField[]; blocks: FormTemplateBlock[] }

