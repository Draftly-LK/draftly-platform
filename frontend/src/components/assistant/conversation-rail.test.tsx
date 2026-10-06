// @vitest-environment happy-dom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { ConversationRail } from "./conversation-rail";

const conversations = [
  { id: "rconv-1", title: "Double sale and prior registration", createdAt: "2026-10-06T03:00:00Z" },
  { id: "rconv-2", title: "Transfer of a registered parcel", createdAt: "2026-09-30T03:00:00Z" },
];

function renderRail(props: Partial<Parameters<typeof ConversationRail>[0]> = {}) {
  const handlers = {
    onSelect: vi.fn(),
    onCreate: vi.fn(),
    onRename: vi.fn(async () => {}),
    onRemove: vi.fn(async () => {}),
  };
  renderWithIntl(
    <ConversationRail conversations={conversations} selectedId="rconv-1" {...handlers} {...props} />,
  );
  // The rail opens collapsed; expand it to reach the list.
  fireEvent.click(screen.getByRole("button", { name: "Expand conversations" }));
  return handlers;
}

function openActions(title: string) {
  fireEvent.click(screen.getByRole("button", { name: `Conversation actions: ${title}` }));
}

describe("conversation rail actions", () => {
  it("shows the creation date under each title", () => {
    renderRail();
    expect(screen.getByText("Oct 06")).toBeTruthy();
    expect(screen.getByText("Sep 30")).toBeTruthy();
  });

  it("renames a conversation with Enter and trims the new title", async () => {
    const { onRename } = renderRail();
    openActions("Transfer of a registered parcel");
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    const field = screen.getByLabelText("Conversation name");
    fireEvent.change(field, { target: { value: "  RTA transfer notes  " } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(onRename).toHaveBeenCalledTimes(1));
    expect(onRename).toHaveBeenCalledWith("rconv-2", "RTA transfer notes");
  });

  it("does not save an empty or unchanged name, and Escape cancels", () => {
    const { onRename } = renderRail();
    openActions("Transfer of a registered parcel");
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    const field = screen.getByLabelText("Conversation name");
    fireEvent.change(field, { target: { value: "   " } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onRename).not.toHaveBeenCalled();

    openActions("Transfer of a registered parcel");
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    fireEvent.change(screen.getByLabelText("Conversation name"), { target: { value: "Changed" } });
    fireEvent.keyDown(screen.getByLabelText("Conversation name"), { key: "Escape" });
    expect(onRename).not.toHaveBeenCalled();
    expect(screen.getByText("Transfer of a registered parcel")).toBeTruthy();
  });

  it("asks before removing, and Cancel keeps the conversation", async () => {
    const { onRemove } = renderRail();
    openActions("Double sale and prior registration");
    fireEvent.click(screen.getByRole("menuitem", { name: "Remove from list" }));
    expect(screen.getByText("Remove this conversation from your list?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onRemove).not.toHaveBeenCalled();

    openActions("Double sale and prior registration");
    fireEvent.click(screen.getByRole("menuitem", { name: "Remove from list" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(onRemove).toHaveBeenCalledWith("rconv-1"));
  });

  it("has no actions menu when rename and remove are not available", () => {
    renderRail({ onRename: undefined, onRemove: undefined });
    expect(screen.queryByRole("button", { name: /Conversation actions/ })).toBeNull();
  });
});
