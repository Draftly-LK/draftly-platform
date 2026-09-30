// @vitest-environment happy-dom
import { Editor } from "@tiptap/core";
import { afterEach, describe, expect, it } from "vitest";
import { form08Document } from "./english/form-08";
import { form12Document } from "./english/form-12";
import { GAZETTE_NODES, GAZETTE_TEMPLATE_LOAD, GazetteLock, GzSlot } from "./schema";

let editor: Editor | null = null;

function mount(content = form08Document) {
  editor = new Editor({ extensions: [...GAZETTE_NODES, GzSlot, GazetteLock], content });
  return editor;
}

afterEach(() => {
  editor?.destroy();
  editor = null;
});

describe("gazette template lock", () => {
  it("parses both templates against the schema without dropping content", () => {
    for (const content of [form08Document, form12Document]) {
      const instance = new Editor({ extensions: [...GAZETTE_NODES, GzSlot, GazetteLock], content });
      expect(instance.getJSON()).toEqual(content);
      instance.destroy();
    }
  });

  it("refuses typing, deleting, and replacing the prescribed wording", () => {
    const instance = mount();
    const before = instance.getJSON();
    const inside = 5;
    expect(instance.commands.insertContentAt(inside, "altered")).toBe(true);
    expect(instance.getJSON()).toEqual(before);
    instance.commands.deleteRange({ from: 2, to: 40 });
    expect(instance.getJSON()).toEqual(before);
    instance.commands.selectAll();
    instance.commands.deleteSelection();
    expect(instance.getJSON()).toEqual(before);
    instance.commands.setContent("<p>replaced</p>");
    expect(instance.getJSON()).toEqual(before);
  });

  it("refuses removing a blank or changing what it is bound to", () => {
    const instance = mount();
    const before = instance.getJSON();
    let slotPos = -1;
    instance.state.doc.descendants((node, pos) => {
      if (slotPos === -1 && node.type.name === "gzSlot") slotPos = pos;
    });
    expect(slotPos).toBeGreaterThan(0);
    instance.view.dispatch(instance.state.tr.setNodeAttribute(slotPos, "field", "transferee_name"));
    instance.view.dispatch(instance.state.tr.delete(slotPos, slotPos + 1));
    expect(instance.getJSON()).toEqual(before);
  });

  it("refuses paste, drop, and text input at the view", () => {
    const instance = mount();
    const plugin = instance.state.plugins.find((candidate) => candidate.props.handlePaste);
    expect(plugin).toBeDefined();
    const props = plugin!.props as Record<string, (...args: unknown[]) => boolean>;
    expect(props.handlePaste!()).toBe(true);
    expect(props.handleDrop!()).toBe(true);
    expect(props.handleTextInput!()).toBe(true);
  });

  it("allows an explicit template load", () => {
    const instance = mount();
    const tr = instance.state.tr
      .replaceWith(0, instance.state.doc.content.size, instance.schema.nodeFromJSON(form12Document).content)
      .setMeta(GAZETTE_TEMPLATE_LOAD, true);
    instance.view.dispatch(tr);
    expect(instance.getJSON()).toEqual(form12Document);
  });
});
