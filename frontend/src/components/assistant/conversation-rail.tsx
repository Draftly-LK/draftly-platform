"use client";

import {
  Archive,
  Ellipsis,
  MessageSquare,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Search,
  X,
} from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Menu, type MenuItem } from "@/components/ui/menu";

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
  /** ISO timestamp; shown as a short date under the title when present. */
  createdAt?: string;
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
  onRename,
  onRemove,
}: {
  conversations: ResearchConversation[];
  selectedId: string;
  onSelect: (id: string) => void;
  onCreate: () => void;
  /** With these, each row gets a menu to rename it or remove it from the list. */
  onRename?: (id: string, title: string) => Promise<void>;
  onRemove?: (id: string) => Promise<void>;
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
          className="bg-scrim absolute inset-0 z-10 lg:hidden"
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
              variant="secondary"
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
              <span className="border-border-control bg-canvas focus-within:bg-surface focus-within:border-forest focus-within:ring-4 focus-within:ring-border-active flex min-h-9 items-center gap-2 rounded-control border px-3">
                <Search
                  className="text-muted-ink size-4 shrink-0"
                  strokeWidth={1.5}
                />
                <input
                  ref={searchRef}
                  id="research-conversation-search"
                  name="researchConversationSearch"
                  className="min-w-0 flex-1 bg-transparent text-sm outline-none focus-visible:outline-none"
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
              visible.map((item) => (
                <ConversationRow
                  key={item.id}
                  item={item}
                  selected={item.id === selectedId}
                  onSelect={() => {
                    onSelect(item.id);
                    closeIfOverlay();
                  }}
                  onRename={onRename}
                  onRemove={onRemove}
                />
              ))
            )}
          </div>
        </div>
      </aside>
    </>
  );
}

function ConversationRow({
  item,
  selected,
  onSelect,
  onRename,
  onRemove,
}: {
  item: ResearchConversation;
  selected: boolean;
  onSelect: () => void;
  onRename?: (id: string, title: string) => Promise<void>;
  onRemove?: (id: string) => Promise<void>;
}) {
  const t = useTranslations("research");
  const format = useFormatter();
  const [mode, setMode] = useState<"view" | "rename" | "confirm">("view");
  const [draft, setDraft] = useState(item.title);
  const [pending, setPending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLDivElement>(null);
  const rowRef = useRef<HTMLButtonElement>(null);
  // After rename or remove-cancel, focus goes back to the row, not the page.
  const returnFocus = useRef(false);

  useEffect(() => {
    if (mode === "rename") inputRef.current?.select();
    if (mode === "confirm") confirmRef.current?.querySelector("button")?.focus();
    if (mode === "view" && returnFocus.current) {
      returnFocus.current = false;
      rowRef.current?.focus();
    }
  }, [mode]);

  function backToView() {
    returnFocus.current = true;
    setMode("view");
  }

  async function saveRename() {
    // Enter and the blur that follows it both arrive here; save once.
    if (pending || mode !== "rename") return;
    const title = draft.trim();
    if (!onRename || !title || title === item.title) {
      backToView();
      return;
    }
    setPending(true);
    try {
      await onRename(item.id, title);
    } finally {
      setPending(false);
      backToView();
    }
  }

  async function confirmRemove() {
    if (!onRemove || pending) return;
    setPending(true);
    try {
      await onRemove(item.id);
    } finally {
      setPending(false);
      setMode("view");
    }
  }

  if (mode === "rename") {
    return (
      <div className="p-1">
        <label className="sr-only" htmlFor={`rename-${item.id}`}>
          {t("conversationName")}
        </label>
        <input
          ref={inputRef}
          id={`rename-${item.id}`}
          className="border-forest ring-border-active text-ink bg-surface min-h-9 w-full rounded border px-2 text-sm ring-4 focus-visible:outline-none"
          value={draft}
          maxLength={256}
          disabled={pending}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => void saveRename()}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void saveRename();
            } else if (event.key === "Escape") {
              // Escape cancels the rename only; it must not also close the drawer.
              event.stopPropagation();
              setDraft(item.title);
              backToView();
            }
          }}
        />
      </div>
    );
  }

  if (mode === "confirm") {
    return (
      <div
        ref={confirmRef}
        role="group"
        aria-label={t("removeConfirm")}
        className="border-border bg-canvas rounded border p-2"
      >
        <p className="text-ink text-sm">{t("removeConfirm")}</p>
        <p className="text-muted-ink mt-0.5 truncate text-xs">{item.title}</p>
        <div className="mt-2 flex justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={pending}
            onClick={backToView}
          >
            {t("cancelAction")}
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            loading={pending}
            onClick={() => void confirmRemove()}
          >
            {t("removeConfirmAction")}
          </Button>
        </div>
      </div>
    );
  }

  const actions: MenuItem[] = [];
  if (onRename) {
    actions.push({
      key: "rename",
      label: t("renameConversation"),
      icon: Pencil,
      onSelect: () => {
        setDraft(item.title);
        setMode("rename");
      },
    });
  }
  if (onRemove) {
    actions.push({
      key: "remove",
      label: t("removeConversation"),
      icon: Archive,
      tone: "danger",
      onSelect: () => setMode("confirm"),
    });
  }

  return (
    <div
      className={`flex items-center rounded ${
        selected
          ? "bg-selected-bg text-forest font-semibold"
          : "text-ink hover:bg-hover-bg"
      }`}
    >
      <button
        ref={rowRef}
        type="button"
        aria-current={selected ? "true" : undefined}
        onClick={onSelect}
        title={item.title}
        className="focus-visible:outline-ring flex min-h-10 min-w-0 flex-1 items-center gap-2 rounded px-2 py-1.5 text-left text-sm"
      >
        <MessageSquare
          aria-hidden="true"
          className={`size-4 shrink-0 ${selected ? "" : "text-muted-ink"}`}
          strokeWidth={1.5}
        />
        <span className="min-w-0 flex-1">
          <span className="block truncate">{item.title}</span>
          {item.createdAt ? (
            <time
              dateTime={item.createdAt}
              className="text-muted-ink block text-xs font-normal tabular-nums"
            >
              {format.dateTime(new Date(item.createdAt), {
                day: "2-digit",
                month: "short",
              })}
            </time>
          ) : null}
        </span>
      </button>
      {actions.length > 0 ? (
        <Menu
          label={`${t("conversationActions")}: ${item.title}`}
          trigger={
            <Ellipsis aria-hidden="true" className="size-4" strokeWidth={1.5} />
          }
          triggerClassName="text-muted-ink hover:text-ink hover:bg-hover-bg mr-1 flex size-8 items-center justify-center rounded-control"
          // The list scrolls and clips, so the menu is drawn above the page.
          portalWhen={() => true}
          items={actions}
        />
      ) : null}
    </div>
  );
}
