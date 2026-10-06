// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatComposer } from "./chat-composer";

afterEach(cleanup);

function Harness({ onSubmit, busy = false, initial = "" }: { onSubmit: () => void; busy?: boolean; initial?: string }) {
  const [value, setValue] = useState(initial);
  return (
    <ChatComposer
      id="q"
      label="Question"
      placeholder="Ask a legal research question…"
      value={value}
      onChange={setValue}
      onSubmit={onSubmit}
      sendLabel="Send"
      busyLabel="Checking authorities…"
      busy={busy}
    />
  );
}

describe("chat composer", () => {
  it("starts as one line with an icon-only send button", () => {
    render(<Harness onSubmit={vi.fn()} />);
    const field = screen.getByLabelText("Question");
    expect(field.getAttribute("rows")).toBe("1");
    const send = screen.getByRole("button", { name: "Send" });
    expect(send.textContent).toBe("");
    expect((send as HTMLButtonElement).disabled).toBe(true);
  });

  it("sends with Enter and keeps Shift+Enter for a new line", () => {
    const onSubmit = vi.fn();
    render(<Harness onSubmit={onSubmit} initial="What governs a transfer?" />);
    const field = screen.getByLabelText("Question");
    fireEvent.keyDown(field, { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("does not send while an input method is still composing", () => {
    const onSubmit = vi.fn();
    render(<Harness onSubmit={onSubmit} initial="පනත" />);
    fireEvent.keyDown(screen.getByLabelText("Question"), { key: "Enter", isComposing: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does not send an empty question or while busy", () => {
    const onSubmit = vi.fn();
    const { unmount } = render(<Harness onSubmit={onSubmit} initial="   " />);
    fireEvent.keyDown(screen.getByLabelText("Question"), { key: "Enter" });
    unmount();
    render(<Harness onSubmit={onSubmit} initial="A question" busy />);
    fireEvent.keyDown(screen.getByLabelText("Question"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Checking authorities…" })).toBeTruthy();
  });
});
