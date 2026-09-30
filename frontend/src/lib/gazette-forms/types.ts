import type { JSONContent } from "@tiptap/core";

export type GazetteLanguage = "en" | "si";

export interface GazetteForm {
  /** Backend template id this rendering belongs to. */
  templateId: string;
  formNumber: string;
  /** The language edition of the gazette this rendering transcribes. */
  language: GazetteLanguage;
  document: JSONContent;
  /** Gazette page images, relative to docs/reference/forms/pages/<language>. */
  pages: string[];
}

export interface SlotInfo {
  id: string;
  /** Backend field id, when the blank renders a bound field. */
  field: string | null;
  multiline: boolean;
  /** `gazette.slot.*` key, for blanks inside running prose and tables. */
  labelKey: string | null;
  /** The printed caption before the blank, verbatim (entries only). */
  caption: string | null;
  /** The printed title of the numbered item the blank sits in. */
  itemTitle: string | null;
  itemNumber: string | null;
}

function textOf(nodes: JSONContent[] | undefined): string {
  return (nodes ?? [])
    .map((node) => (node.type === "text" ? (node.text ?? "") : node.type === "hardBreak" ? " " : ""))
    .join("");
}

function tidyCaption(value: string): string | null {
  const tidy = value.replace(/\.{2,}/g, "").replace(/[\s:-]+$/u, "").trim();
  return tidy.length > 0 ? tidy : null;
}

/** Every blank in document order: the order field-by-field review walks. */
export function listSlots(document: JSONContent): SlotInfo[] {
  const slots: SlotInfo[] = [];
  const visit = (node: JSONContent, itemNumber: string | null, itemTitle: string | null) => {
    let number = itemNumber;
    let title = itemTitle;
    if (node.type === "gzItem") {
      number = String(node.attrs?.number ?? "");
      const first = node.content?.[0];
      title = first ? tidyCaption(textOf(first.content)) : null;
    }
    const children = node.content ?? [];
    children.forEach((child, index) => {
      if (child.type === "gzSlot") {
        const attrs = child.attrs ?? {};
        slots.push({
          id: String(attrs.id),
          field: (attrs.field as string | null) ?? null,
          multiline: Boolean(attrs.multiline),
          labelKey: (attrs.labelKey as string | null) ?? null,
          caption: attrs.labelKey ? null : tidyCaption(textOf(children.slice(0, index))),
          itemTitle: title,
          itemNumber: number,
        });
      } else {
        visit(child, number, title);
      }
    });
  };
  visit(document, null, null);
  return slots;
}
