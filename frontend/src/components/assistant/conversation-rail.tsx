"use client";

import {
  MessageSquare,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";

/**
 * Conversation list for the research assistant.
 *
 * The interaction shape (rail, new conversation, search, selected state) follows
 * the assistant pattern described in `backend/docs/services/research-service.md`
 * §2.1. No LibreChat source is copied here, so no third-party notice is
 * required; if components are later ported verbatim, §2.1 step 5 applies.
 *
 * The rail always opens collapsed to an icon strip (a row below 1024 px) so the
 * thread has the width. Expanded, it sits beside the thread on wide screens and
 * slides in over the page as a drawer on narrow ones, like the main sidebar.
 */
export interface ResearchConversation {
  id: string;
  title: string;
}

/** Below Tailwind 'lg' the expanded rail is an overlay drawer, not a column. */
function isOverlayViewport(): boolean {
  return window.matchMedia("(max-width: 1023.98px)").matches;
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
  const t = useTranslations("research");
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState(true);
  const [focusSearch, setFocusSearch] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!collapsed && focusSearch) {
      searchRef.current?.focus();
      setFocusSearch(false);
    }
  }, [collapsed, focusSearch]);

  // Escape closes the drawer on narrow screens, where it covers the page.
  useEffect(() => {
    if (collapsed) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && isOverlayViewport()) setCollapsed(true);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [collapsed]);

  /** A drawer gets out of the way once the choice is made; a column stays. */
  function closeIfOverlay() {
    if (isOverlayViewport()) setCollapsed(true);
  }

  const needle = query.trim().toLowerCase();
  const visible =
    needle.length === 0
      ? conversations
      : conversations.filter((item) =>
          item.title.toLowerCase().includes(needle),
        );

  return (
    <>
      {/* The strip stays in the page flow; on narrow screens it also stays put
          while the drawer is open, so the thread does not jump. */}
      <aside
        aria-label={t("conversations")}
        className={`border-border bg-surface border-b p-2 lg:w-14 lg:border-b-0 lg:border-r ${collapsed ? "" : "lg:hidden"}`}
      >
        <div className="flex items-center gap-1 lg:sticky lg:top-2 lg:flex-col">
          <IconButton
            label={t("expandConversations")}
            aria-expanded={!collapsed}
            aria-controls="conversation-rail-panel"
            onClick={() => setCollapsed(false)}
          >
            <PanelLeftOpen className="size-5" strokeWidth={1.5} />
          </IconButton>
          <IconButton label={t("newConversation")} onClick={onCreate}>
            <MessageSquarePlus className="size-5" strokeWidth={1.5} />
          </IconButton>
          <IconButton
            label={t("searchConversations")}
            onClick={() => {
              setFocusSearch(true);
              setCollapsed(false);
            }}
          >
            <Search className="size-5" strokeWidth={1.5} />
          </IconButton>
        </div>
      </aside>

      {!collapsed && (
        <button
          type="button"
          aria-label={t("collapseConversations")}
          tabIndex={-1}
          className="bg-ink/25 absolute inset-0 z-10 lg:hidden"
          onClick={() => setCollapsed(true)}
        />
      )}

      {/* Narrow screens: a drawer sliding in from the left over the thread,
          below the page header so the title and profile stay visible.
          Wide screens: a column beside the thread. */}
      <aside
        id="conversation-rail-panel"
        aria-label={t("conversations")}
        aria-hidden={collapsed}
        className={`border-border bg-surface shadow-popover absolute inset-y-0 left-0 z-10 flex w-[min(300px,85vw)] flex-col border-r transition-[transform,visibility] duration-200 ease-out lg:static lg:z-auto lg:w-[272px] lg:shadow-none lg:transition-none ${
          collapsed
            ? "invisible -translate-x-full lg:hidden"
            : "visible translate-x-0"
        }`}
      >
        <div className="flex min-h-0 flex-1 flex-col lg:sticky lg:top-0 lg:max-h-screen lg:flex-none">
          <div className="flex items-center gap-2 px-4 pb-2 pt-3">
            <h2 className="text-muted-ink min-w-0 flex-1 truncate text-xs font-semibold">
              {t("conversations")}
            </h2>
            <IconButton
              label={t("collapseConversations")}
              aria-expanded={!collapsed}
              aria-controls="conversation-rail-panel"
              className="size-8"
              onClick={() => setCollapsed(true)}
            >
              <PanelLeftClose className="size-4" strokeWidth={1.5} />
            </IconButton>
          </div>
          <div className="space-y-2 px-4">
            <Button
              type="button"
              variant="primary"
              onClick={() => {
                onCreate();
                closeIfOverlay();
              }}
              className="w-full"
            >
              <MessageSquarePlus className="size-4" strokeWidth={1.5} />
              {t("newConversation")}
            </Button>
            <label className="block">
              <span className="sr-only">{t("searchConversations")}</span>
              <span className="border-border-control bg-canvas focus-within:bg-surface focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ring flex min-h-9 items-center gap-2 rounded-control border px-3">
                <Search
                  className="text-muted-ink size-4 shrink-0"
                  strokeWidth={1.5}
                />
                <input
                  ref={searchRef}
                  id="research-conversation-search"
                  name="researchConversationSearch"
                  className="min-w-0 flex-1 bg-transparent text-sm outline-none"
                  placeholder={t("searchConversations")}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") setQuery("");
                  }}
                />
                {query && (
                  <button
                    type="button"
                    aria-label={t("clearSearch")}
                    title={t("clearSearch")}
                    onClick={() => setQuery("")}
                    className="text-muted-ink hover:text-ink rounded-control"
                  >
                    <X className="size-4" strokeWidth={1.5} />
                  </button>
                )}
              </span>
            </label>
          </div>
          {/* Scrolls on its own so a long history cannot push the thread down. */}
          <div className="border-border mt-3 min-h-0 flex-1 space-y-0.5 overflow-y-auto border-t px-2 py-2">
            {visible.length === 0 ? (
              <p className="text-muted-ink px-2 py-3 text-sm">
                {t("noConversations")}
              </p>
            ) : (
              visible.map((item) => {
                const selected = item.id === selectedId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-current={selected ? "true" : undefined}
                    onClick={() => {
                      onSelect(item.id);
                      closeIfOverlay();
                    }}
                    title={item.title}
                    className={`focus-visible:outline-ring flex min-h-10 w-full items-center gap-2 rounded px-2 text-left text-sm ${
                      selected
                        ? "bg-selected-bg text-forest font-semibold"
                        : "text-ink hover:bg-hover-bg"
                    }`}
                  >
                    <MessageSquare
                      aria-hidden="true"
                      className={`size-4 shrink-0 ${selected ? "" : "text-muted-ink"}`}
                      strokeWidth={1.5}
                    />
                    <span className="min-w-0 flex-1 truncate">
                      {item.title}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
