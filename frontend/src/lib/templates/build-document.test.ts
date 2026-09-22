import { describe, expect, it } from "vitest";
import { facts as seededFacts, templates } from "@/lib/mocks";
import type { EditorDocument, FormTemplate, VerifiedFact } from "@/types";
import { buildTemplateDocument } from "./build-document";

const TEMPLATE: FormTemplate = {
  id: "template-synthetic",
  formNumber: "Form S",
  nameKey: "draft.syntheticName",
  regime: "rta",
  transactionType: "transfer",
  approvalState: "approved",
  fields: [
    // Declared out of order: the draft must follow `order`, not the array.
    { id: "field-b", labelKey: "facts.b", order: 2, required: true, factBinding: "b" },
    { id: "field-a", labelKey: "facts.a", order: 1, required: true, factBinding: "a" },
    { id: "field-c", labelKey: "facts.c", order: 3, required: false, factBinding: "c" },
  ],
  blocks: [
    { id: "block-s-closing", order: 3, kind: "locked-prescribed", placeholderText: "SYNTHETIC CLOSING" },
    { id: "block-s-parcel", order: 2, kind: "editable", placeholderText: "" },
    { id: "block-s-heading", order: 1, kind: "locked-prescribed", placeholderText: "SYNTHETIC HEADING" },
    { id: "block-s-empty", order: 4, kind: "editable", placeholderText: "" },
  ],
};

function fact(key: string, state: VerifiedFact["verificationState"]): VerifiedFact {
  return {
    id: `fact-${key}`,
    matterId: "matter-synthetic",
    key,
    labelKey: `facts.${key}`,
    section: "parcel",
    value: `Synthetic ${key}`,
    extractedValue: `Synthetic ${key}`,
    confidence: 0.99,
    verificationState: state,
    changes: [],
  };
}

interface AnyNode {
  type: string;
  attrs?: Record<string, unknown>;
  text?: string;
  content?: AnyNode[];
}

/** Every node in the document, depth first. */
function walk(nodes: readonly AnyNode[] | undefined): AnyNode[] {
  return (nodes ?? []).flatMap((node) => [node, ...walk(node.content)]);
}

const nodes = (doc: EditorDocument) => walk(doc.content as AnyNode[]);
const chips = (doc: EditorDocument) =>
  nodes(doc).flatMap((node) => (node.type === "factChip" ? [node.attrs?.fact_id] : []));
const texts = (doc: EditorDocument) =>
  nodes(doc).flatMap((node) => (node.type === "text" ? [node.text] : []));

const ALL_USABLE = [fact("a", "verified"), fact("b", "corrected"), fact("c", "verified")];

describe("buildTemplateDocument", () => {
  it("opens with the form's title as a level-1 heading", () => {
    const doc = buildTemplateDocument(TEMPLATE, ALL_USABLE, {
      "draft.syntheticName": "Synthetic form",
    });

    expect(doc.content[0]).toMatchObject({ type: "heading", attrs: { level: 1 } });
    expect(texts(doc)[0]).toBe("Synthetic form");
  });

  it("falls back to the form number when no title label is given", () => {
    expect(texts(buildTemplateDocument(TEMPLATE, ALL_USABLE))[0]).toContain("Form S");
  });

  it("keeps prescribed blocks locked, verbatim, and in template order", () => {
    const doc = buildTemplateDocument(TEMPLATE, ALL_USABLE);

    const locked = (doc.content as AnyNode[]).filter((node) => node.type === "lockedBlock");
    expect(locked.map((node) => node.attrs?.template_block_id)).toEqual([
      "block-s-heading",
      "block-s-closing",
    ]);
    expect(walk(locked).flatMap((node) => (node.text ? [node.text] : []))).toEqual([
      "SYNTHETIC HEADING",
      "SYNTHETIC CLOSING",
    ]);
  });

  it("puts each section's fields between the blocks around it", () => {
    const types = buildTemplateDocument(TEMPLATE, ALL_USABLE).content.map((node) => node.type);

    expect(types).toEqual([
      "heading",
      "lockedBlock",
      "heading",
      "paragraph",
      "paragraph",
      "paragraph",
      "lockedBlock",
    ]);
  });

  it("orders fields by their declared order", () => {
    expect(chips(buildTemplateDocument(TEMPLATE, ALL_USABLE))).toEqual([
      "fact-a",
      "fact-b",
      "fact-c",
    ]);
  });

  it.each(["verified", "corrected"] as const)(
    "a %s fact becomes a chip carrying its state",
    (state) => {
      const doc = buildTemplateDocument(TEMPLATE, [fact("a", state)]);

      const chip = nodes(doc).find((node) => node.type === "factChip");
      expect(chip?.attrs).toEqual({ fact_id: "fact-a", verification_state: state });
    },
  );

  it.each(["unreviewed", "conflict"] as const)(
    "a %s fact is a placeholder, never a chip",
    (state) => {
      const doc = buildTemplateDocument(TEMPLATE, [fact("a", state), fact("b", "verified")]);

      expect(chips(doc)).toEqual(["fact-b"]);
      expect(texts(doc)).toContain("— pending verification —");
      expect(texts(doc).join(" ")).not.toContain("Synthetic a");
    },
  );

  it("never copies a fact's value into the text, only its reference", () => {
    const doc = buildTemplateDocument(TEMPLATE, ALL_USABLE);

    expect(texts(doc).join(" ")).not.toMatch(/Synthetic [abc]/);
  });

  it("skips an editable section with no bound facts", () => {
    const doc = buildTemplateDocument(TEMPLATE, []);

    expect(doc.content.map((node) => node.type)).toEqual([
      "heading",
      "lockedBlock",
      "lockedBlock",
    ]);
  });

  it("uses the caller's labels for field names and the pending text", () => {
    const doc = buildTemplateDocument(TEMPLATE, [fact("a", "unreviewed")], {
      "facts.a": "Synthetic A",
      "draft.fieldPending": "Synthetic pending",
    });

    expect(texts(doc)).toEqual(expect.arrayContaining(["Synthetic A: ", "Synthetic pending"]));
  });

  it("does not reorder the template it was given", () => {
    const before = structuredClone(TEMPLATE);

    buildTemplateDocument(TEMPLATE, ALL_USABLE);

    expect(TEMPLATE).toEqual(before);
  });

  it("the shipped Form 8 template chips every usable demo fact it binds", () => {
    const form8 = templates[0];
    if (!form8) throw new Error("expected the Form 8 fixture");
    const bound = new Set(form8.fields.map((field) => field.factBinding));
    const usable = seededFacts.filter(
      (f) =>
        bound.has(f.key) &&
        (f.verificationState === "verified" || f.verificationState === "corrected"),
    );

    const doc = buildTemplateDocument(form8, seededFacts);

    expect(new Set(chips(doc))).toEqual(new Set(usable.map((f) => f.id)));
  });
});
