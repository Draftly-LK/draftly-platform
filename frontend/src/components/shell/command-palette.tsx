"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { FileText, Home, Library, Search, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  demoOnly,
  documents as documentFixtures,
  facts as factFixtures,
  matters as matterFixtures,
} from "@/lib/mocks";
import { IconButton } from "@/components/ui/icon-button";

const libraryFixtures = ["SYN-RTA-REF-01", "SYN-GAZ-02"];

export function CommandPalette({
  compact = false,
  tone = "light",
}: {
  compact?: boolean;
  /** `dark` for the navy navigation rail. */
  tone?: "light" | "dark";
}) {
  // Fixture matters/documents/facts are demo-only; with the API configured the
  // palette lists no records (it still offers navigation and the library).
  const matters = demoOnly(matterFixtures);
  const documents = demoOnly(documentFixtures);
  const facts = demoOnly(factFixtures);
  const libraryItems = demoOnly(libraryFixtures);
  const t = useTranslations("shell");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  const navigate = (href: string) => {
    setOpen(false);
    router.push(href);
  };
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        {compact ? (
          <IconButton label={t("search")}>
            <Search className="size-5" strokeWidth={1.5} />
          </IconButton>
        ) : (
          <button
            aria-label={t("search")}
            className={
              tone === "dark"
                ? "text-on-dark-muted hover:text-on-dark flex h-10 w-full items-center gap-1.5 rounded-control border border-white/15 bg-white/[0.04] px-2.5 text-left text-sm hover:border-white/25 hover:bg-white/[0.08] rail:mx-auto rail:w-10 rail:justify-center rail:gap-0 rail:px-0"
                : "border-border-strong bg-surface text-muted-ink hover:bg-hover-bg flex h-10 w-full items-center gap-1.5 rounded-control border px-3 text-left text-sm"
            }
          >
            <Search className="size-4" strokeWidth={1.5} />
            <span className="min-w-0 flex-1 truncate rail:hidden">{t("search")}</span>
            <kbd
              className={`shrink-0 rounded-full border px-1 font-sans text-xs leading-4 rail:hidden ${tone === "dark" ? "border-border-on-dark" : "border-border"}`}
            >
              {t("searchShortcut")}
            </kbd>
          </button>
        )}
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="bg-scrim fixed inset-0 z-40" />
        <Dialog.Content
          aria-describedby={undefined}
          className="rounded-dialog border-border-strong bg-surface shadow-dialog fixed left-1/2 top-[14vh] z-40 w-[min(640px,calc(100vw-32px))] -translate-x-1/2 border p-2"
        >
          <Dialog.Title className="sr-only">{t("search")}</Dialog.Title>
          <Command className="bg-transparent">
            {/* The search row: 16px sides, 14px top and bottom, 12px between icon and text, all centred on one line. The soft bottom rule marks it as the active row. */}
            <div className="flex items-center gap-3 border-b border-border-active px-4 py-3.5">
              <Search aria-hidden="true" className="text-muted-ink size-5 shrink-0" strokeWidth={1.5} />
              {/* No ring of its own: this input is the only thing focused while the palette is open, and the caret shows it. (An exception to the focus-ring rule; the global ring is declared after Tailwind utilities, so the variant is needed.) */}
              <Command.Input
                className="h-6 min-w-0 flex-1 border-0 bg-transparent p-0 outline-none focus-visible:outline-none"
                placeholder={t("searchPlaceholder")}
              />
              <Dialog.Close asChild>
                <IconButton label={t("close")} className="-my-2 -mr-2.5 shrink-0">
                  <X className="size-5" strokeWidth={1.5} />
                </IconButton>
              </Dialog.Close>
            </div>
            <Command.List className="max-h-[420px] overflow-y-auto p-2">
              <Command.Empty className="text-muted-ink p-6 text-center">
                {t("searchEmpty")}
              </Command.Empty>
              <Command.Group
                heading={t("commands")}
                className="text-muted-ink text-xs"
              >
                <CommandItem icon={<Home />} onSelect={() => navigate("/")}>
                  {t("goHome")}
                </CommandItem>
                <CommandItem
                  icon={<Sparkles />}
                  onSelect={() => navigate("/assistant")}
                >
                  {t("openAssistant")}
                </CommandItem>
              </Command.Group>
              {matters.length > 0 && (
                <Command.Group
                  heading={t("matters")}
                  className="text-muted-ink text-xs"
                >
                  {matters.map((matter) => (
                    <CommandItem
                      key={matter.id}
                      icon={<FileText />}
                      onSelect={() => navigate(`/matters/${matter.id}`)}
                    >
                      {matter.reference}
                    </CommandItem>
                  ))}
                </Command.Group>
              )}
              {documents.length + facts.length + libraryItems.length > 0 && (
                <Command.Group
                  heading={t("search")}
                  className="text-muted-ink text-xs"
                >
                  {documents.map((document) => (
                    <CommandItem
                      key={document.id}
                      icon={<FileText />}
                      onSelect={() =>
                        navigate(
                          `/matters/${document.matterId}/documents?document=${document.id}`,
                        )
                      }
                    >
                      {document.fileName}
                    </CommandItem>
                  ))}
                  {facts.map((fact) => (
                    <CommandItem
                      key={fact.id}
                      icon={<Search />}
                      onSelect={() =>
                        navigate(
                          `/matters/${fact.matterId}/facts?fact=${fact.id}`,
                        )
                      }
                    >
                      {String(fact.value ?? fact.key)}
                    </CommandItem>
                  ))}
                  {libraryItems.map((item) => (
                    <CommandItem
                      key={item}
                      icon={<Library />}
                      onSelect={() => navigate(`/library?q=${item}`)}
                    >
                      {item}
                    </CommandItem>
                  ))}
                </Command.Group>
              )}
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function CommandItem({
  icon,
  children,
  onSelect,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="text-ink data-[selected=true]:bg-selected-bg mt-1 flex min-h-10 cursor-pointer items-center gap-2 rounded px-3 text-sm outline-none [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:stroke-[1.5]"
    >
      {icon}
      {children}
    </Command.Item>
  );
}
