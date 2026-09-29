"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { gazetteFormFor, listSlots } from "@/lib/gazette-forms";
import { cn } from "@/lib/utils";
import { GazetteContext, type GazetteContextValue } from "./gazette-context";

const GazetteDocument = dynamic(() => import("./gazette-document"), { ssr: false });

/**
 * Development-only review aid: the printed gazette pages beside the Tiptap
 * rendering, drawn plain (dotted blanks, no values), for layout comparison.
 */
export function GazetteCompare({ templateId }: { templateId: string }) {
  const t = useTranslations("gazette");
  const gazette = gazetteFormFor(templateId)!;
  const [plain, setPlain] = useState(true);
  const slots = useMemo(
    () => Object.fromEntries(listSlots(gazette.document).map((slot) => [slot.id, slot])),
    [gazette.document],
  );
  const context = useMemo<GazetteContextValue>(
    () => ({
      values: {},
      setValue: () => undefined,
      fields: {},
      slots,
      activeSlotId: null,
      activate: () => undefined,
      readOnly: true,
      plain,
    }),
    [slots, plain],
  );
  return (
    <main className="bg-canvas min-h-screen p-4">
      <div className="mb-3 flex items-center gap-3">
        <h1 className="text-lg font-semibold">{t("compareTitle", { form: gazette.formNumber })}</h1>
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={plain} onChange={(event) => setPlain(event.target.checked)} />
          {t("comparePlain")}
        </label>
      </div>
      <div className="grid grid-cols-[794px_794px] gap-4" data-compare>
        <div className="space-y-4" data-compare-source>
          {gazette.pages.map((page) => (
            // eslint-disable-next-line @next/next/no-img-element -- dev-only page image served by a route handler.
            <img key={page} src={`/dev/gazette-page/${page}`} alt={page} width={794} className="bg-surface block w-[794px]" />
          ))}
        </div>
        <div className={cn("border-border-strong self-start border")} data-compare-render>
          <GazetteContext.Provider value={context}>
            <GazetteDocument document={gazette.document} />
          </GazetteContext.Provider>
        </div>
      </div>
    </main>
  );
}
