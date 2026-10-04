// @vitest-environment happy-dom
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";

// The real AccountMenu reads Clerk; the view it renders is what is under test.
vi.mock("@clerk/nextjs", () => ({ Show: () => null, useClerk: () => ({}), useUser: () => ({}) }));

import { AccountMenuView } from "./account-menu";

const open = () => fireEvent.click(screen.getByRole("button", { name: "Account menu" }));

describe("AccountMenuView", () => {
  it("lists Profile, Settings, Billing, Help, then a divider and Sign out, in that order", () => {
    const { container } = renderWithIntl(<AccountMenuView name="Praveen De Silva" onSignOut={() => undefined} />);
    open();
    const entries = [...container.querySelectorAll("[role='menu'] > *")].map((el) =>
      el.getAttribute("role") === "separator" ? "---" : el.textContent?.trim(),
    );
    expect(entries).toEqual(["My profile", "Settings", "Billing", "Help", "---", "Sign out"]);
  });

  it("sends Settings, Billing and Help to their pages", () => {
    renderWithIntl(<AccountMenuView name="P" onSignOut={() => undefined} />);
    open();
    const href = (name: string) => screen.getByRole("menuitem", { name }).getAttribute("href");
    expect(href("Settings")).toBe("/settings");
    expect(href("Billing")).toBe("/billing");
    expect(href("Help")).toBe("/help");
  });

  it("runs sign out when chosen", () => {
    const onSignOut = vi.fn();
    renderWithIntl(<AccountMenuView name="P" onSignOut={onSignOut} />);
    open();
    fireEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));
    expect(onSignOut).toHaveBeenCalledOnce();
  });

  it("offline there is no session to end: no Sign out and no stray divider", () => {
    const { container } = renderWithIntl(<AccountMenuView name="" />);
    open();
    expect(screen.queryByRole("menuitem", { name: "Sign out" })).toBeNull();
    expect(container.querySelector("[role='separator']")).toBeNull();
    expect(screen.getAllByRole("menuitem")).toHaveLength(4);
  });

  it("arrow keys skip the divider", () => {
    renderWithIntl(<AccountMenuView name="P" onSignOut={() => undefined} />);
    open();
    const items = screen.getAllByRole("menuitem");
    const help = items[3] as HTMLElement;
    help.focus();
    fireEvent.keyDown(help, { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[4]);
    expect(items[4]?.textContent?.trim()).toBe("Sign out");
  });
});
