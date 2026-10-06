"use client";

import { ExternalLink, GitBranch, LoaderCircle, Search, Send, ShieldAlert, Square, TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { ConversationRail } from "./conversation-rail";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { InlineAlert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { RowsSkeleton } from "@/components/ui/skeleton";
import { archiveResearchConversation, createResearchConversation, branchResearchMessage, listResearchConversations, listResearchMessages, renameResearchConversation, sendResearchMessage } from "@/lib/api/research";
import { ApiError, isApiEnabled, type TokenProvider } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { AssistantScope, ResearchCitation, ResearchConversation, ResearchMessage, ResearchSources } from "@/types";

const LIBRARY_SCOPE: AssistantScope = { type: "library", labelKey: "research.scope.library" };

/**
 * `useTokenProvider` calls Clerk's `useAuth`, which requires a `ClerkProvider`.
 * The offline demo runs without one, so the hook lives in a component that is
 * only mounted when the backend is configured. Offline, no request is made, so
 * the token provider is never called.
 */
export function ResearchScreen() {
  return isApiEnabled() ? <ApiBoundResearchScreen /> : <ResearchFlow getToken={offlineToken} />;
}

const offlineToken: TokenProvider = () => Promise.resolve(null);

function ApiBoundResearchScreen() {
  const getToken = useTokenProvider();
  return <ResearchFlow getToken={getToken} />;
}

function ResearchFlow({ getToken }: { getToken: TokenProvider }) {
  const t = useTranslations("research");
  const [conversations, setConversations] = useState<ResearchConversation[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [messages, setMessages] = useState<ResearchMessage[]>([]);
  const [question, setQuestion] = useState("");
  // Statutes by default, as before case law was available.
  const [sources, setSources] = useState<ResearchSources>("statutes");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const apiEnabled = isApiEnabled();
  // Offline there is nothing to load, so the thread is ready at once.
  const [loaded, setLoaded] = useState(!apiEnabled);
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
    } catch (failure) { setError(explain(failure, t("loadFailed"))); } finally { setLoaded(true); }
  }, [apiEnabled, explain, getToken, t]);

  useEffect(() => { void loadConversations(); }, [loadConversations]);
  useEffect(() => {
    if (!selectedId) { setMessages([]); return; }
    void listResearchMessages(getToken, selectedId).then(setMessages).catch((failure: unknown) => setError(explain(failure, t("loadFailed"))));
  }, [explain, getToken, selectedId, t]);

  async function createConversation() {
    // Offline, the page already shows the api-unavailable notice.
    if (!apiEnabled) return;
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
      await sendResearchMessage(getToken, conversationId, content, messages.at(-1)?.id, sources);
      setQuestion("");
      setMessages(await listResearchMessages(getToken, conversationId));
      await loadConversations();
    } catch (failure) { setError(explain(failure, t("sendFailed"))); } finally { setBusy(false); }
  }

  async function renameConversation(id: string, title: string) {
    setError(undefined);
    try {
      const renamed = await renameResearchConversation(getToken, id, title);
      setConversations((rows) => rows.map((row) => (row.id === id ? renamed : row)));
    } catch (failure) { setError(explain(failure, t("renameFailed"))); }
  }

  async function removeConversation(id: string) {
    setError(undefined);
    try {
      await archiveResearchConversation(getToken, id);
      const remaining = conversations.filter((row) => row.id !== id);
      setConversations(remaining);
      // Removing the open conversation moves to the next one, or to an empty thread.
      if (selectedId === id) setSelectedId(remaining[0]?.id);
    } catch (failure) { setError(explain(failure, t("removeFailed"))); }
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
      <div className="relative grid min-h-[calc(100vh-105px)] lg:grid-cols-[auto_minmax(0,1fr)]">
        <ConversationRail conversations={conversations} selectedId={selectedId ?? ""} onSelect={setSelectedId} onCreate={() => void createConversation()} onRename={apiEnabled ? renameConversation : undefined} onRemove={apiEnabled ? removeConversation : undefined} />
        <main className="mx-auto flex w-full max-w-4xl flex-col p-4 md:p-6">
          <SourceSelector value={sources} onChange={setSources} disabled={busy || !apiEnabled} />
          {!apiEnabled && <InlineAlert tone="info" className="mt-4">{t("apiUnavailable")}</InlineAlert>}
          {error && <InlineAlert tone="danger" className="mt-4">{error}</InlineAlert>}
          <section aria-label={t("thread")} className="mt-4 flex-1 space-y-3">
            {!loaded && <RowsSkeleton label={t("loadingConversations")} rows={3} className="border-border bg-surface rounded border" />}
            {loaded && messages.length === 0 && <div className="text-muted-ink py-16 text-center"><ShieldAlert className="mx-auto mb-3 size-8" strokeWidth={1.5} /><p>{t("emptyThread")}</p></div>}
            {messages.map((message) => {
              const insufficient = message.content.startsWith("research.insufficient.");
              const grounded = message.role === "assistant" && !insufficient;
              return (
                <article key={message.id} className={`rounded border p-4 ${message.role === "user" ? "border-border-strong bg-surface ml-auto max-w-[85%]" : insufficient ? "border-border-strong bg-surface border-l-2" : "border-teal bg-teal-bg border-l-2"}`}>
                  <div className={`${message.role === "assistant" ? "text-ink" : "text-muted-ink"} mb-1 flex items-center gap-1.5 text-xs font-semibold`}>
                    {insufficient && <Search className="size-3.5" strokeWidth={1.5} />}
                    {message.role === "user" ? t("you") : insufficient ? t("noSupportingAuthority") : t("answer")}
                  </div>
                  {grounded && message.claims && message.claims.length > 0 ? (
                    <AnswerClaims message={message} />
                  ) : (
                    <p className="whitespace-pre-line leading-7">
                      {!insufficient ? message.content : message.content === "research.insufficient.caseLawUnavailable" ? t("caseLawUnavailable") : t("insufficientAuthority")}
                    </p>
                  )}
                  {message.role === "user" && <Button className="mt-3" onClick={() => void branch(message.id)}><GitBranch className="size-4" />{t("branch")}</Button>}
                  {insufficient && <p className="text-ink mt-2 text-sm">{t("insufficientAction")}</p>}
                  {grounded && message.citations.length > 0 && <AnswerSources citations={message.citations} />}
                </article>
              );
            })}
          </section>
          <form className="border-border-control bg-surface shadow-popover sticky bottom-3 mt-5 rounded border p-3 focus-within:border-forest focus-within:ring-4 focus-within:ring-border-active" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
            <label className="sr-only" htmlFor="research-question">{t("composerLabel")}</label>
            <textarea id="research-question" className="min-h-20 w-full resize-y bg-transparent p-2 outline-none focus-visible:outline-none" placeholder={t("composerPlaceholder")} value={question} onChange={(event) => setQuestion(event.target.value)} disabled={busy || !apiEnabled} />
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

const SOURCE_OPTIONS: ReadonlyArray<{ value: ResearchSources; label: string; help: string }> = [
  { value: "all", label: "sourceAll", help: "sourceHelpAll" },
  { value: "statutes", label: "sourceStatutes", help: "sourceHelpStatutes" },
  { value: "cases", label: "sourceCases", help: "sourceHelpCases" },
];

/** Which legal sources the next question searches. */
function SourceSelector({ value, onChange, disabled }: { value: ResearchSources; onChange: (next: ResearchSources) => void; disabled: boolean }) {
  const t = useTranslations("research");
  const help = SOURCE_OPTIONS.find((option) => option.value === value)?.help ?? "sourceHelpStatutes";
  return (
    <section aria-labelledby="research-source-scope" className="border-border-strong bg-surface rounded border px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 id="research-source-scope" className="text-sm font-semibold">{t("sourceScope")}</h2>
        <div role="group" aria-labelledby="research-source-scope" className="flex flex-wrap gap-2">
          {SOURCE_OPTIONS.map((option) => (
            <Button
              key={option.value}
              type="button"
              size="sm"
              aria-pressed={value === option.value}
              disabled={disabled}
              className={value === option.value ? "border-forest bg-selected-bg text-forest font-semibold" : undefined}
              onClick={() => onChange(option.value)}
            >
              {t(option.label)}
            </Button>
          ))}
        </div>
      </div>
      <p className={`mt-2 flex items-center gap-1.5 text-sm ${value === "cases" ? "text-amber-text" : "text-muted-ink"}`}>
        {value === "cases" ? <TriangleAlert aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.5} /> : null}
        {t(help)}
      </p>
    </section>
  );
}

function kindOf(citation: ResearchCitation): "statute" | "case" {
  return citation.authorityKind ?? (citation.authorityId.toLowerCase().startsWith("commonlii-") ? "case" : "statute");
}

/** One research answer: its claims, each tagged by the kind of source it cites when case law is involved. */
function AnswerClaims({ message }: { message: ResearchMessage }) {
  const t = useTranslations("research");
  const kindById = new Map(message.citations.map((citation) => [citation.authorityId.toUpperCase(), kindOf(citation)]));
  const mixed = message.citations.some((citation) => kindOf(citation) === "case");
  return (
    <div className="space-y-3">
      {(message.claims ?? []).map((claim, index) => {
        const kinds = new Set(claim.citationIds.map((id) => kindById.get(id.toUpperCase())).filter(Boolean));
        return (
          <p key={index} className="leading-7">
            {claim.text}
            {mixed && kinds.has("statute") ? <SourceTag tone="statute">{t("claimStatute")}</SourceTag> : null}
            {mixed && kinds.has("case") ? <SourceTag tone="case">{t("claimCase")}</SourceTag> : null}
          </p>
        );
      })}
    </div>
  );
}

function SourceTag({ tone, children }: { tone: "statute" | "case"; children: string }) {
  return (
    <span className={`rounded-control ml-2 inline-flex items-center border px-1.5 align-middle text-[11px] font-semibold uppercase leading-5 tracking-normal ${tone === "case" ? "border-amber bg-amber-bg text-amber-text" : "border-border-strong bg-surface text-muted-ink"}`}>
      {children}
    </span>
  );
}

/** The answer's sources, grouped: statutes and amendments, then case law with its warning. */
function AnswerSources({ citations }: { citations: ResearchCitation[] }) {
  const t = useTranslations("research");
  // A source cited by several claims is listed once.
  const unique = [...new Map(citations.map((citation) => [citation.authorityId, citation])).values()];
  const statutes = unique.filter((citation) => kindOf(citation) === "statute");
  const cases = unique.filter((citation) => kindOf(citation) === "case");
  return (
    <div className="mt-4 space-y-3">
      <h3 className="text-sm font-semibold">{t("sourcesUsed")}</h3>
      {statutes.length > 0 && (
        <div className="space-y-2">
          {cases.length > 0 && <h4 className="text-muted-ink text-xs font-semibold">{t("sourceStatutes")}</h4>}
          {statutes.map((citation) => (
            <details key={citation.id} className="border-border-strong bg-surface rounded border px-3 py-2">
              <summary className="focus-visible:outline-ring cursor-pointer text-sm font-medium">
                {citation.title && citation.reference ? `${citation.title} — ${citation.reference}` : citation.authorityId}
              </summary>
              <p className="mt-2 text-sm leading-6">{citation.passage}</p>
            </details>
          ))}
        </div>
      )}
      {cases.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-muted-ink text-xs font-semibold">{t("sourceCases")}</h4>
          {cases.map((citation) => (
            <details key={citation.id} className="border-amber bg-surface rounded border border-l-2 px-3 py-2">
              <summary className="focus-visible:outline-ring cursor-pointer text-sm">
                <span className="font-medium">{citation.title || citation.authorityId}</span>
                <span className="text-muted-ink"> — {citation.reference || t("citationNotRecorded")}</span>
                <span className="text-amber-text mt-1 flex items-center gap-1.5 text-xs font-semibold">
                  <TriangleAlert aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={1.5} />
                  {t("caseLead")}
                </span>
              </summary>
              <p className="mt-2 text-sm leading-6">{citation.passage}</p>
              {citation.sourceUrl ? (
                <a href={citation.sourceUrl} target="_blank" rel="noopener noreferrer" className="text-forest mt-2 inline-flex items-center gap-1 text-sm font-medium hover:underline">
                  {t("openSource")}
                  <ExternalLink aria-hidden="true" className="size-3.5" strokeWidth={1.5} />
                </a>
              ) : null}
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
