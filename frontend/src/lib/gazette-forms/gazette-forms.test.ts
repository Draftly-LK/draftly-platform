import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { JSONContent } from "@tiptap/core";
import { describe, expect, it } from "vitest";
import { GAZETTE_FORMS, gazetteFormFor, listSlots } from "./index";
import { SINHALA_GAZETTE_FORMS } from "./sinhala";
import type { GazetteForm } from "./types";

const transcriptionDir = fileURLToPath(
  new URL("../../../../docs/reference/forms/transcriptions/", import.meta.url),
);

function transcription(language: string, formNumber: string): string[] {
  return readFileSync(`${transcriptionDir}${language}/form-${formNumber}.txt`, "utf8")
    .split("\n")
    .filter((line) => line.trim().length > 0);
}

/**
 * Comparison key: dotted leaders are blanks, not wording, and the page's line
 * wrapping and column spacing are layout. Everything else must match exactly.
 */
function key(value: string): string {
  return value.replace(/\.{2,}/g, "").replace(/\s+/gu, "");
}

/** Printed text of every line and cell, split at blanks and line breaks. */
function fragments(node: JSONContent): string[] {
  const out: string[] = [];
  const walk = (current: JSONContent) => {
    if (current.type === "gzItem") out.push(String(current.attrs?.number ?? ""));
    if (current.type === "gzLine" || current.type === "gzCell") {
      let buffer = "";
      for (const child of current.content ?? []) {
        if (child.type === "text") buffer += child.text ?? "";
        else {
          out.push(buffer);
          buffer = "";
        }
      }
      out.push(buffer);
      return;
    }
    (current.content ?? []).forEach(walk);
  };
  walk(node);
  return out.map(key).filter((fragment) => fragment.length > 0);
}

// The served set and the separately kept Sinhala set are both held to their
// own edition's transcription.
const EVERY_EDITION: GazetteForm[] = [
  ...Object.values(GAZETTE_FORMS),
  ...Object.values(SINHALA_GAZETTE_FORMS).filter((form) => GAZETTE_FORMS[form.templateId] !== form),
];

describe.each(EVERY_EDITION)("Gazette form $formNumber ($language)", (form) => {
  const printed = transcription(form.language, form.formNumber);
  const printedKey = printed.map(key).join("");
  const templateKey = fragments(form.document).join("");

  it("uses only wording that the gazette prints", () => {
    for (const fragment of fragments(form.document)) {
      expect(printedKey, `not in the gazette: ${fragment}`).toContain(fragment);
    }
  });

  it("omits no printed wording", () => {
    for (const line of printed) {
      const lineKey = key(line);
      if (lineKey.length === 0) continue;
      expect(templateKey, `missing from the template: ${line}`).toContain(lineKey);
    }
  });

  it("gives every blank a unique id and a way to describe it", () => {
    const slots = listSlots(form.document);
    expect(new Set(slots.map((slot) => slot.id)).size).toBe(slots.length);
    for (const slot of slots) {
      expect(slot.caption ?? slot.labelKey, slot.id).toBeTruthy();
    }
  });

  it("is registered under its backend template id", () => {
    const registered = form.language === "si" ? SINHALA_GAZETTE_FORMS : GAZETTE_FORMS;
    expect(registered[form.templateId]).toBe(form);
  });
});

describe("listSlots", () => {
  it("walks blanks in printed order with their captions", () => {
    const slots = listSlots(GAZETTE_FORMS["rta.reg.2022.form.08"]!.document);
    expect(slots.slice(0, 3).map((slot) => [slot.id, slot.field, slot.caption, slot.itemNumber])).toEqual([
      ["f08.1.a", "district", "(a) District", "1."],
      ["f08.1.aa", "ds_division", "(b) Divisional Secretary’s Division", "1."],
      ["f08.1.ae", "gn_division", "(c) Grama Niladhari Division", "1."],
    ]);
    expect(slots[0]!.itemTitle).toBe("Particulars of Land Parcel");
  });

  it("walks the Sinhala edition the same way, under its own captions", () => {
    const slots = listSlots(SINHALA_GAZETTE_FORMS["rta.reg.2022.form.08"]!.document);
    expect(slots.slice(0, 3).map((slot) => [slot.id, slot.field, slot.caption, slot.itemNumber])).toEqual([
      ["f08.1.a", "district", "(අ) දිස්ත්‍රික්කය", "1."],
      ["f08.1.aa", "ds_division", "(ආ) ප්‍රාදේශීය ලේකම් කොට්ඨාසය", "1."],
      ["f08.1.ae", "gn_division", "(ඇ) ග්‍රාම නිලධාරී කොට්ඨාසය", "1."],
    ]);
    expect(slots[0]!.itemTitle).toBe("ඉඩම් පිළිබඳ විස්තර");
  });

  it("binds every mapped backend field at most once per form", () => {
    for (const form of Object.values(GAZETTE_FORMS)) {
      const fields = listSlots(form.document)
        .map((slot) => slot.field)
        .filter((field): field is string => field !== null);
      expect(new Set(fields).size).toBe(fields.length);
    }
  });

  it("returns undefined for a template with no gazette rendering", () => {
    expect(gazetteFormFor("rta.ops.tire.31")).toBeUndefined();
  });
});
