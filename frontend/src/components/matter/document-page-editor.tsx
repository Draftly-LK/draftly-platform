"use client";

import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import type { FragmentRangeInput } from "@/lib/api/documents";
import type { ApiSourceFile } from "@/types/rta";

export function DocumentPageEditor({
  sources,
  ranges,
  onChange,
  disabled,
}: {
  sources: ApiSourceFile[];
  ranges: FragmentRangeInput[];
  onChange: (ranges: FragmentRangeInput[]) => void;
  disabled: boolean;
}) {
  const t = useTranslations("documentOperations");
  function change(index: number, update: Partial<FragmentRangeInput>) {
    onChange(
      ranges.map((range, position) =>
        position === index ? { ...range, ...update } : range,
      ),
    );
  }
  function move(index: number, offset: number) {
    const next = [...ranges];
    const from = next[index],
      to = next[index + offset];
    if (!from || !to) return;
    [next[index], next[index + offset]] = [to, from];
    onChange(next);
  }
  const available = sources.filter(
    (source) => source.state !== "SUPERSEDED" && source.pageCount !== null,
  );
  return (
    <fieldset disabled={disabled} className="space-y-3">
      <legend className="mb-2 text-sm font-medium">{t("ranges")}</legend>
      {ranges.map((range, index) => (
        <div
          key={index}
          className="border-border grid grid-cols-2 items-end gap-3 rounded border p-3 sm:grid-cols-4"
        >
          <label className="col-span-2 text-sm">
            {t("source")}
            <select
              className="border-border-control bg-surface rounded-control mt-1 min-h-10 w-full border px-3"
              value={range.sourceFileId}
              onChange={(e) => change(index, { sourceFileId: e.target.value })}
            >
              {available.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.originalFilename}
                </option>
              ))}
            </select>
          </label>
          {(["pageStart", "pageEnd"] as const).map((key) => (
            <label key={key} className="text-sm">
              {t(key)}
              <input
                type="number"
                min={1}
                max={
                  sources.find((source) => source.id === range.sourceFileId)
                    ?.pageCount ?? undefined
                }
                step={1}
                value={range[key] || ""}
                onChange={(e) =>
                  change(index, { [key]: Number(e.target.value) })
                }
                className="border-border-control bg-surface rounded-control mt-1 min-h-10 w-full border px-3"
              />
            </label>
          ))}
          <div className="col-span-2 flex gap-2 sm:col-span-4">
            <Button
              size="sm"
              disabled={disabled || index === 0}
              aria-label={t("moveUp")}
              onClick={() => move(index, -1)}
            >
              <ArrowUp className="size-4" aria-hidden="true" />
            </Button>
            <Button
              size="sm"
              disabled={disabled || index === ranges.length - 1}
              aria-label={t("moveDown")}
              onClick={() => move(index, 1)}
            >
              <ArrowDown className="size-4" aria-hidden="true" />
            </Button>
            <Button
              size="sm"
              disabled={disabled || ranges.length === 1}
              onClick={() =>
                onChange(ranges.filter((_, position) => position !== index))
              }
            >
              <X className="size-4" aria-hidden="true" />
              {t("removeRange")}
            </Button>
          </div>
        </div>
      ))}
      <Button
        size="sm"
        disabled={disabled || available.length === 0}
        onClick={() =>
          available[0] &&
          onChange([
            ...ranges,
            { sourceFileId: available[0].id, pageStart: 1, pageEnd: 1 },
          ])
        }
      >
        <Plus className="size-4" aria-hidden="true" />
        {t("addRange")}
      </Button>
    </fieldset>
  );
}

export function validPageRanges(
  ranges: FragmentRangeInput[],
  sources: ApiSourceFile[],
) {
  const pages = new Set<string>();
  return (
    ranges.length > 0 &&
    ranges.every((range) => {
      const source = sources.find((item) => item.id === range.sourceFileId);
      if (
        !source ||
        source.state === "SUPERSEDED" ||
        !source.pageCount ||
        !Number.isSafeInteger(range.pageStart) ||
        !Number.isSafeInteger(range.pageEnd) ||
        range.pageStart < 1 ||
        range.pageEnd < range.pageStart ||
        range.pageEnd > source.pageCount
      )
        return false;
      for (let page = range.pageStart; page <= range.pageEnd; page++) {
        const key = `${source.id}:${page}`;
        if (pages.has(key)) return false;
        pages.add(key);
      }
      return true;
    })
  );
}
