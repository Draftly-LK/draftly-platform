import { apiFetch, type TokenProvider } from "./client";
import type { AssistantScope, ResearchConversation, ResearchJob, ResearchMessage } from "@/types";

interface List<T> { items: T[] }

export async function listResearchConversations(getToken: TokenProvider, query?: string): Promise<ResearchConversation[]> {
  const suffix = query ? `?query=${encodeURIComponent(query)}` : "";
  return (await apiFetch<List<ResearchConversation>>(`/api/v1/research/conversations${suffix}`, { getToken })).items;
}

export function createResearchConversation(getToken: TokenProvider, scope: AssistantScope, title?: string): Promise<ResearchConversation> {
  return apiFetch("/api/v1/research/conversations", { method: "POST", getToken, body: { scope: { type: scope.type, targetId: scope.targetId }, title } });
}

export function renameResearchConversation(getToken: TokenProvider, conversationId: string, title: string): Promise<ResearchConversation> {
  return apiFetch(`/api/v1/research/conversations/${conversationId}`, { method: "PATCH", getToken, body: { title } });
}

/** Hides the conversation from the list; the server keeps its messages and answers. */
export function archiveResearchConversation(getToken: TokenProvider, conversationId: string): Promise<void> {
  return apiFetch(`/api/v1/research/conversations/${conversationId}/archive`, { method: "POST", getToken });
}

export async function listResearchMessages(getToken: TokenProvider, conversationId: string): Promise<ResearchMessage[]> {
  return (await apiFetch<List<ResearchMessage>>(`/api/v1/research/conversations/${conversationId}/messages`, { getToken })).items;
}

export function sendResearchMessage(getToken: TokenProvider, conversationId: string, content: string, parentMessageId?: string): Promise<ResearchJob> {
  return apiFetch(`/api/v1/research/conversations/${conversationId}/messages`, { method: "POST", getToken, headers: { "Idempotency-Key": crypto.randomUUID() }, body: { content, parentMessageId } });
}

export function branchResearchMessage(getToken: TokenProvider, messageId: string): Promise<{ id: string }> {
  return apiFetch(`/api/v1/research/messages/${messageId}/branch`, { method: "POST", getToken, body: {} });
}
