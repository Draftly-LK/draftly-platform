import type {
  EditorDocument,
  EditorLockedNode,
  EditorParagraphNode,
  FormTemplate,
  FormTemplateBlock,
  VerifiedFact,
} from "@/types";
import { isFactUsable } from "./readiness";

/**
 * Editable blocks are named `block-<form>-<section>` and collect the fields
 * whose bound fact carries that `section`, so the generated instrument follows
 * the form's own section order without a second mapping table to maintain.
 */
function sectionOf(block: FormTemplateBlock): string {
  return block.id.split("-").slice(2).join("-");
}

function lockedNode(block: FormTemplateBlock): EditorLockedNode {
  return {
    type: "lockedBlock",
    attrs: { template_block_id: block.id },
    content: [{ type: "paragraph", content: [{ type: "text", text: block.placeholderText }] }],
  };
}

/**
 * Builds the Form 8 draft from its template: prescribed wording stays locked
 * and untouched, and every bound particular is emitted as a FactChip so the
 * draft carries its provenance rather than a flattened string.
 *
 * `labels` maps a field/section `labelKey` to its localized text; the caller
 * resolves it so this stays free of React and usable inside the store.
 */
export function buildTemplateDocument(
  template: FormTemplate,
  facts: VerifiedFact[],
  labels: Record<string, string> = {},
): EditorDocument {
  const byKey = new Map(facts.map((fact) => [fact.key, fact]));
  const label = (key: string, fallback: string) => labels[key] ?? fallback;
  const fields = [...template.fields].sort((a, b) => a.order - b.order);

  const content: EditorDocument["content"] = [
    {
      type: "heading",
      attrs: { level: 1 },
      content: [
        {
          type: "text",
          text: label(template.nameKey, `${template.formNumber} — instrument of transfer`),
        },
      ],
    },
  ];

  for (const block of [...template.blocks].sort((a, b) => a.order - b.order)) {
    if (block.kind === "locked-prescribed") {
      content.push(lockedNode(block));
      continue;
    }

    const section = sectionOf(block);
    const sectionFields = fields.filter((field) => {
      const fact = field.factBinding ? byKey.get(field.factBinding) : undefined;
      return fact?.section === section;
    });
    if (sectionFields.length === 0) continue;

    content.push({
      type: "heading",
      attrs: { level: 2 },
      content: [{ type: "text", text: label(`sections.${section}`, section) }],
    });

    for (const field of sectionFields) {
      const fact = field.factBinding ? byKey.get(field.factBinding) : undefined;
      const paragraph: EditorParagraphNode = {
        type: "paragraph",
        content: [
          { type: "text", text: `${label(field.labelKey, field.id)}: ` },
        ],
      };

      if (fact && isFactUsable(fact)) {
        paragraph.content?.push({
          type: "factChip",
          attrs: {
            fact_id: fact.id,
            verification_state: fact.verificationState as "verified" | "corrected",
          },
        });
      } else {
        paragraph.content?.push({
          type: "text",
          text: label("draft.fieldPending", "— pending verification —"),
        });
      }

      content.push(paragraph);
    }
  }

  return { type: "doc", content };
}
