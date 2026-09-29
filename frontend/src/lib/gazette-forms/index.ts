import type { JSONContent } from "@tiptap/core";
import { form08Document } from "./form-08";
import { form12Document } from "./form-12";

export interface GazetteForm {
  /** Backend template id this rendering belongs to. */
  templateId: string;
  formNumber: string;
  document: JSONContent;
  /** Gazette page images, relative to docs/reference/forms/pages. */
  pages: string[];
}

/**
 * Gazette renderings keyed by backend template id. A template without an entry
 * falls back to the field-by-field review only; nothing is guessed.
 *
 * The rendering is transcribed from Gazette 1886/58 (2014). The backend cites
 * the 2022 amendment for the same form numbers; whether the 2014 layout is the
 * current prescribed one is for the legal team to confirm.
 */
export const GAZETTE_FORMS: Record<string, GazetteForm> = {
  "rta.reg.2022.form.08": {
    templateId: "rta.reg.2022.form.08",
    formNumber: "08",
    document: form08Document,
    pages: ["page-04.png", "page-05.png", "page-06.png"],
  },
  "rta.reg.2022.form.12": {
    templateId: "rta.reg.2022.form.12",
    formNumber: "12",
    document: form12Document,
    pages: ["page-13.png", "page-14.png"],
  },
};

export function gazetteFormFor(templateId: string): GazetteForm | undefined {
  return GAZETTE_FORMS[templateId];
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
