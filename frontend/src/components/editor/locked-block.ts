import { Node, mergeAttributes } from "@tiptap/core";

export const LockedBlock = Node.create({
  name: "lockedBlock",
  group: "block",
  content: "block+",
  defining: true,
  isolating: true,
  addAttributes() { return { template_block_id: { default: null } }; },
  parseHTML: () => [{ tag: "section[data-locked-block]" }],
  renderHTML({ HTMLAttributes }) { return ["section", mergeAttributes(HTMLAttributes, { "data-locked-block": "", contenteditable: "false", class: "locked-block" }), 0]; },
});

