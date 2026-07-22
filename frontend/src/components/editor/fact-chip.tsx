"use client";

import { Node, mergeAttributes } from "@tiptap/core";
import {
  NodeViewWrapper,
  ReactNodeViewRenderer,
  type NodeViewProps,
} from "@tiptap/react";
import type { VerifiedFact } from "@/types";

interface FactChipOptions {
  facts: VerifiedFact[];
}

export function canInsertFact(
  fact: Pick<VerifiedFact, "verificationState">,
): boolean {
  return (
    fact.verificationState === "verified" ||
    fact.verificationState === "corrected"
  );
}

export const FactChip = Node.create<FactChipOptions>({
  name: "factChip",
  group: "inline",
  inline: true,
  atom: true,
  addOptions: () => ({ facts: [] }),
  addAttributes() {
    return {
      fact_id: { default: null },
      verification_state: { default: null },
    };
  },
  parseHTML: () => [{ tag: "span[data-fact-chip]" }],
  renderHTML({ HTMLAttributes }) {
    return ["span", mergeAttributes(HTMLAttributes, { "data-fact-chip": "" })];
  },
  addNodeView() {
    return ReactNodeViewRenderer(FactChipView);
  },
});

function FactChipView({ node, extension }: NodeViewProps) {
  const options = extension.options as FactChipOptions;
  const factId = String(node.attrs.fact_id);
  const fact = options.facts.find((item) => item.id === factId);
  const source = fact?.evidence
    ? `${fact.evidence.documentId} · ${fact.evidence.page} · ${fact.evidence.snippet}`
    : factId;
  return (
    <NodeViewWrapper
      as="span"
      data-fact-chip=""
      data-source={source}
      title={source}
      className="border-forest bg-soft-green text-forest mx-0.5 inline-flex cursor-help items-center rounded-full border px-2 py-0.5 align-baseline text-sm font-medium"
    >
      {String(fact?.value ?? factId)}
    </NodeViewWrapper>
  );
}
