// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Tooltip } from "./tooltip";

afterEach(cleanup);

const tip = () => document.body.querySelector("[data-tooltip]");
const settle = () => new Promise((resolve) => setTimeout(resolve, 30));

describe("Tooltip", () => {
  it("appears on keyboard focus with its shortcut, outside the trigger's own tree", async () => {
    render(
      <Tooltip label="Collapse sidebar" shortcut="Ctrl+\">
        <button>go</button>
      </Tooltip>,
    );
    expect(tip()).toBeNull();
    fireEvent.focus(screen.getByRole("button", { name: "go" }));
    await settle();
    expect(tip()?.textContent).toContain("Collapse sidebar");
    expect(tip()?.textContent).toContain("Ctrl+\\");
    expect(tip()?.parentElement).toBe(document.body);
    expect(tip()?.getAttribute("aria-hidden")).toBe("true");
  });

  it("hides on blur and on Escape", async () => {
    render(
      <Tooltip label="Home">
        <button>go</button>
      </Tooltip>,
    );
    const button = screen.getByRole("button", { name: "go" });
    fireEvent.focus(button);
    await settle();
    expect(tip()).not.toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(tip()).toBeNull();
    fireEvent.focus(button);
    await settle();
    expect(tip()).not.toBeNull();
    fireEvent.blur(button);
    expect(tip()).toBeNull();
  });

  it("hides when the trigger is clicked, so it does not linger beside an open menu", async () => {
    render(
      <Tooltip label="Account">
        <button>go</button>
      </Tooltip>,
    );
    const button = screen.getByRole("button", { name: "go" });
    fireEvent.focus(button);
    await settle();
    expect(tip()).not.toBeNull();
    fireEvent.click(button);
    expect(tip()).toBeNull();
  });

  it("stays away when its enabled check says no (the sidebar is not a rail)", async () => {
    render(
      <Tooltip label="Home" enabled={() => false}>
        <button>go</button>
      </Tooltip>,
    );
    fireEvent.focus(screen.getByRole("button", { name: "go" }));
    await settle();
    expect(tip()).toBeNull();
  });
});
