"use client";

import { GitBranch, LoaderCircle, RotateCcw, Search, Send, ShieldAlert, Square } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { ConversationRail } from "./conversation-rail";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { createResearchConversation, branchResearchMessage, listResearchConversations, listResearchMessages, sendResearchMessage } from "@/lib/api/research";
import { ApiError, isApiEnabled } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { AssistantScope, ResearchConversation, ResearchMessage } from "@/types";

const LIBRARY_SCOPE: AssistantScope = { type: "library", labelKey: "research.scope.library" };

export function ResearchScreen() {
  const t = useTranslations("research");
  const getToken = useTokenProvider();
  const [conversations, setConversations] = useState<ResearchConversation[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [messages, setMessages] = useState<ResearchMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const apiEnabled = isApiEnabled();
  // A 403 `feature_denied` is not a failure of the feature: the account has no
  // plan that includes research. Say so instead of a generic error.
  const explain = useCallback(
    (failure: unknown, fallback: string) =>
      failure instanceof ApiError && failure.code === "feature_denied" ? t("notEnabled") : fallback,
    [t],
  );

  const loadConversations = useCallback(async () => {
    if (!apiEnabled) return;
    try {
      const rows = await listResearchConversations(getToken);
      setConversations(rows);
      setSelectedId((current) => current ?? rows[0]?.id);
    } catch (failure) { setError(explain(failure, t("loadFailed"))); }
  }, [apiEnabled, explain, getToken, t]);

  useEffect(() => { void loadConversations(); }, [loadConversations]);
  useEffect(() => {
    if (!selectedId) { setMessages([]); return; }
    void listResearchMessages(getToken, selectedId).then(setMessages).catch((failure: unknown) => setError(explain(failure, t("loadFailed"))));
  }, [explain, getToken, selectedId, t]);

  async function createConversation() {
    if (!apiEnabled) { setError(t("apiUnavailable")); return; }
    setBusy(true); setError(undefined);
    try {
      const created = await createResearchConversation(getToken, LIBRARY_SCOPE);
      setConversations((rows) => [created, ...rows]);
      setSelectedId(created.id); setMessages([]);
    } catch (failure) { setError(explain(failure, t("createFailed"))); } finally { setBusy(false); }
  }

  async function submit() {
    const content = question.trim();
    if (!content || busy) return;
    setBusy(true); setError(undefined);
    try {
      let conversationId = selectedId;
      if (!conversationId) {
        const created = await createResearchConversation(getToken, LIBRARY_SCOPE, content.slice(0, 80));
        setConversations((rows) => [created, ...rows]);
        setSelectedId(created.id); conversationId = created.id;
      }
      await sendResearchMessage(getToken, conversationId, content, messages.at(-1)?.id);
      setQuestion("");
      setMessages(await listResearchMessages(getToken, conversationId));
      await loadConversations();
    } catch (failure) { setError(explain(failure, t("sendFailed"))); } finally { setBusy(false); }
  }

  async function branch(messageId: string) {
    setBusy(true);
    try { await branchResearchMessage(getToken, messageId); }
    catch (failure) { setError(explain(failure, t("branchFailed"))); }
    finally { setBusy(false); }
  }

  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="grid min-h-[calc(100vh-105px)] min-[1024px]:grid-cols-[260px_minmax(0,1fr)]">
        <ConversationRail conversations={conversations} selectedId={selectedId ?? ""} onSelect={setSelectedId} onCreate={() => void createConversation()} />
        <main className="mx-auto flex w-full max-w-4xl flex-col p-4 md:p-6">
          <div className="border-border-strong bg-surface rounded border px-4 py-3 text-sm">
            <strong>{t("libraryScope")}</strong>
            <span className="text-muted-ink ml-2">{t("corpusLimit")}</span>
          </div>
          {!apiEnabled && <Notice text={t("apiUnavailable")} />}
          {error && <Notice text={error} />}
          <section aria-label={t("thread")} className="mt-4 flex-1 space-y-3">
            {messages.length === 0 && <div className="text-muted-ink py-16 text-center"><ShieldAlert className="mx-auto mb-3 size-8" strokeWidth={1.5} /><p>{t("emptyThread")}</p></div>}
            {messages.map((message) => {
              const insufficient = message.content.startsWith("research.insufficient.");
              const grounded = message.role === "assistant" && !insufficient;
              return (
                <article key={message.id} className={`rounded border p-4 ${message.role === "user" ? "border-border-strong bg-surface ml-auto max-w-[85%]" : insufficient ? "border-border-strong bg-surface border-l-2" : "border-teal bg-teal-bg border-l-2"}`}>
                  <div className={`${message.role === "assistant" ? "text-ink" : "text-muted-ink"} mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase`}>
                    {insufficient && <Search className="size-3.5" strokeWidth={1.5} />}
                    {message.role === "user" ? t("you") : insufficient ? t("noMatch") : t("answer")}
                  </div>
                  <p className="whitespace-pre-line leading-7">{insufficient ? t("insufficientAuthority") : message.content}</p>
                  {message.role === "user" && <Button className="mt-3" onClick={() => void branch(message.id)}><GitBranch className="size-4" />{t("branch")}</Button>}
                  {insufficient && <p className="text-ink mt-2 text-sm">{t("insufficientAction")}</p>}
                  {grounded && message.citations.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <h3 className="text-sm font-semibold">{t("citations")}</h3>
                      {message.citations.map((citation) => (
                        <details key={citation.id} className="border-border-strong bg-surface rounded border px-3 py-2">
                          <summary className="focus-visible:outline-ring cursor-pointer text-sm font-medium">
                            {citation.authorityId} · {citation.verified ? t("verified") : t("unverified")}
                          </summary>
                          <p className="mt-2 text-sm leading-6">{citation.passage}</p>
                        </details>
                      ))}
                    </div>
                  )}
                </article>
              );
            })}
          </section>
          <form className="border-border-strong bg-surface shadow-popover sticky bottom-3 mt-5 rounded border p-3" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
            <label className="sr-only" htmlFor="research-question">{t("composerLabel")}</label>
            <textarea id="research-question" className="min-h-20 w-full resize-y bg-transparent p-2 outline-none" placeholder={t("composerPlaceholder")} value={question} onChange={(event) => setQuestion(event.target.value)} disabled={busy || !apiEnabled} />
            <div className="border-border flex items-center border-t pt-3">
              {busy && <span className="text-muted-ink flex items-center gap-2 text-sm"><LoaderCircle className="size-4 animate-spin" />{t("working")}</span>}
              <Button type="submit" variant="primary" className="ml-auto" disabled={!question.trim() || busy || !apiEnabled}>{busy ? <Square className="size-4" /> : <Send className="size-4" />}{busy ? t("stop") : t("send")}</Button>
            </div>
          </form>
        </main>
      </div>
    </AppShell>
  );
}

function Notice({ text }: { text: string }) {
  return <div role="status" className="border-amber bg-amber-bg text-amber-text mt-4 flex items-center gap-2 border-l-2 p-3 text-sm"><RotateCcw className="size-4" />{text}</div>;
}
