import { answers, crossChecks, obligations, questionSets, questions, templates, users } from "@/lib/mocks";
import { useDemoStore } from "@/lib/store/demo-store";
import type { AuditEvent, Check, CrossCheck, Draft, FormTemplate, GroundedAnswer, Matter, MatterDocument, Obligation, Question, QuestionSet, User, VerifiedFact, Workflow } from "@/types";

export const MOCK_LATENCY_MS = 80;
const wait = () => new Promise<void>((resolve) => setTimeout(resolve, MOCK_LATENCY_MS));

// TODO(api): GET /api/users/me
export async function getCurrentUser(): Promise<User> { await wait(); const user = users[0]; if (!user) throw new Error("Missing deterministic demo user"); return structuredClone(user); }
// TODO(api): GET /api/matters
export async function getMatters(): Promise<Matter[]> { await wait(); return structuredClone(useDemoStore.getState().matters); }
// TODO(api): GET /api/matters/{matterId}
export async function getMatter(matterId: string): Promise<Matter | undefined> { await wait(); return structuredClone(useDemoStore.getState().matters.find((matter) => matter.id === matterId)); }
// TODO(api): GET /api/matters/{matterId}/documents
export async function getDocuments(matterId: string): Promise<MatterDocument[]> { await wait(); return structuredClone(useDemoStore.getState().documents.filter((document) => document.matterId === matterId)); }
// TODO(api): GET /api/matters/{matterId}/facts
export async function getFacts(matterId: string): Promise<VerifiedFact[]> { await wait(); return structuredClone(useDemoStore.getState().facts.filter((fact) => fact.matterId === matterId)); }
// TODO(api): GET /api/matters/{matterId}/checks
export async function getChecks(matterId: string): Promise<Check[]> { await wait(); return structuredClone(useDemoStore.getState().checks.filter((check) => check.matterId === matterId)); }
// TODO(api): GET /api/matters/{matterId}/cross-checks
export async function getCrossChecks(matterId: string): Promise<CrossCheck[]> { await wait(); return structuredClone(crossChecks.filter((check) => check.matterId === matterId)); }
// TODO(api): GET /api/matters/{matterId}/workflows
export async function getWorkflows(matterId: string): Promise<Workflow[]> { await wait(); void matterId; return structuredClone(useDemoStore.getState().workflows); }
// TODO(api): GET /api/assistant/answers
export async function getAnswers(): Promise<GroundedAnswer[]> { await wait(); return structuredClone(answers); }
// TODO(api): GET /api/matters/{matterId}/drafts
export async function getDrafts(matterId: string): Promise<Draft[]> { await wait(); return structuredClone(useDemoStore.getState().drafts.filter((draft) => draft.matterId === matterId)); }
// TODO(api): GET /api/templates
export async function getTemplates(): Promise<FormTemplate[]> { await wait(); return structuredClone(templates); }
// TODO(api): GET /api/obligations
export async function getObligations(): Promise<Obligation[]> { await wait(); return structuredClone(obligations); }
// TODO(api): GET /api/questions
export async function getQuestions(): Promise<Question[]> { await wait(); return structuredClone(questions); }
// TODO(api): GET /api/question-sets
export async function getQuestionSets(): Promise<QuestionSet[]> { await wait(); return structuredClone(questionSets); }
// TODO(api): GET /api/history
export async function getAuditEvents(matterId?: string): Promise<AuditEvent[]> { await wait(); const events = useDemoStore.getState().auditEvents; return structuredClone(matterId ? events.filter((event) => event.matterId === matterId) : events); }

