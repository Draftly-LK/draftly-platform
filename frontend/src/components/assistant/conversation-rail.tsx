"use client";

import { MessageSquarePlus, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

/**
 * Conversation list for the research assistant.
 *
 * The interaction shape (rail, new conversation, search, selected state) follows
 * the assistant pattern described in `backend/docs/services/research-service.md`
 * §2.1. No LibreChat source is copied here, so no third-party notice is
 * required; if components are later ported verbatim, §2.1 step 5 applies.
 */
export interface ResearchConversation {
  id: string;
  title: string;
  /** Seeded demonstration thread rather than a real past conversation. */
  seeded: boolean;
}

export function ConversationRail({
  conversations,
  selectedId,
  onSelect,
  onCreate,
}: {
  conversations: ResearchConversation[];
  selectedId: string;
  onSelect: (id: string) => void;
  onCreate: () => void;
}) {
  const t = useTranslations("assistant");
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const visible =
    needle.length === 0
      ? conversations
      : conversations.filter((item) => item.title.toLowerCase().includes(needle));

  return (
    <aside
      aria-label={t("conversations")}
      className="border-border bg-canvas flex flex-col border-b p-4 min-[1280px]:max-h-[calc(100vh-105px)] min-[1280px]:border-b-0 min-[1280px]:border-r"
    >
      <button
        type="button"
        onClick={onCreate}
        className="border-border-strong bg-surface hover:bg-hover-bg focus-visible:outline-ring flex min-h-10 items-center gap-2 rounded border px-3 font-medium"
      >
        <MessageSquarePlus className="size-4" strokeWidth={1.5} />
        {t("newConversation")}
      </button>
      <label className="mt-3 block">
        <span className="sr-only">{t("searchConversations")}</span>
        <span className="border-border-strong bg-surface flex min-h-10 items-center gap-2 rounded border px-3">
          <Search className="text-muted-ink size-4" strokeWidth={1.5} />
          <input
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
            placeholder={t("searchConversations")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </span>
      </label>
      {/* Scrolls on its own so a long history cannot push the thread down. */}
      <div className="mt-3 min-h-0 flex-1 space-y-1 overflow-y-auto">
        {visible.length === 0 ? (
          <p className="text-muted-ink px-1 text-sm">{t("noConversations")}</p>
        ) : (
          visible.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-current={item.id === selectedId ? "true" : undefined}
              onClick={() => onSelect(item.id)}
              className={`block w-full rounded px-3 py-2 text-left text-sm ${
                item.id === selectedId
                  ? "bg-selected-bg text-forest font-semibold"
                  : "hover:bg-hover-bg"
              }`}
            >
              <span className="block truncate">{item.title}</span>
              {item.seeded && (
                <span className="text-muted-ink mt-0.5 block text-xs font-normal">
                  {t("conversationSeeded")}
                </span>
              )}
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
