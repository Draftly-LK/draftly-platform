// @vitest-environment happy-dom
import { fireEvent, screen } from "@testing-library/react";
import { Check } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { Button } from "./button";
import { Card } from "./card";
import { Divider } from "./divider";
import { EmptyState } from "./empty-state";
import { Input, Select, Textarea } from "./field";
import { IconButton } from "./icon-button";
import { ListRow } from "./list-row";
import { Menu } from "./menu";
import { SectionHeader } from "./section-header";
import { StatusChip } from "./status-chip";

describe("Button", () => {
  it("uses navy text on the gold primary, never white", () => {
    renderWithIntl(<Button variant="primary">Save</Button>);
    const classes = screen.getByRole("button", { name: "Save" }).className;
    expect(classes).toContain("bg-gold");
    expect(classes).toContain("text-navy-950");
    expect(classes).not.toContain("text-white");
  });

  it("does not default to type=button, so form buttons keep submitting", () => {
    renderWithIntl(<Button>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" }).getAttribute("type")).toBeNull();
  });

  it("while loading, shows a spinner, announces busy and ignores clicks", () => {
    const onClick = vi.fn();
    renderWithIntl(
      <Button loading onClick={onClick}>
        Saving
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Saving" });
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(button.querySelector("svg.animate-spin")).not.toBeNull();
  });

  it("runs onClick normally and applies the small size", () => {
    const onClick = vi.fn();
    renderWithIntl(
      <Button size="sm" variant="destructive" onClick={onClick}>
        Remove
      </Button>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onClick).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Remove" }).className).toContain("min-h-8");
  });
});

describe("IconButton", () => {
  it("takes its accessible name from label", () => {
    renderWithIntl(<IconButton label="Close">x</IconButton>);
    expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();
  });
});

describe("fields", () => {
  it("ties label, help text and control together", () => {
    renderWithIntl(<Input label="Reference" help="As printed" />);
    const input = screen.getByLabelText("Reference");
    const describedBy = input.getAttribute("aria-describedby") ?? "";
    expect(describedBy).not.toBe("");
    expect(document.getElementById(describedBy)?.textContent).toBe("As printed");
    expect(input.getAttribute("aria-invalid")).toBeNull();
  });

  it("an error replaces help, is marked invalid and carries an icon", () => {
    const { container } = renderWithIntl(<Input label="Reference" help="As printed" error="Enter a reference" />);
    const input = screen.getByLabelText("Reference");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(screen.queryByText("As printed")).toBeNull();
    expect(document.getElementById(input.getAttribute("aria-describedby") ?? "")?.textContent).toBe(
      "Enter a reference",
    );
    expect(container.querySelector("p svg[aria-hidden='true']")).not.toBeNull();
  });

  it("every control draws a 3:1 boundary", () => {
    renderWithIntl(
      <>
        <Input label="A" />
        <Select label="B">
          <option>x</option>
        </Select>
        <Textarea label="C" />
      </>,
    );
    for (const name of ["A", "B", "C"]) {
      expect(screen.getByLabelText(name).className).toContain("border-border-control");
    }
  });
});

describe("StatusChip", () => {
  it("always renders an icon beside its text", () => {
    const { container } = renderWithIntl(
      <StatusChip tone="success" icon={Check}>
        Confirmed
      </StatusChip>,
    );
    expect(container.textContent).toBe("Confirmed");
    expect(container.querySelector("svg[aria-hidden='true']")).not.toBeNull();
    expect(container.firstElementChild?.className).toContain("bg-success-bg");
  });
});

describe("layout pieces", () => {
  it("EmptyState shows heading, one line and an action", () => {
    renderWithIntl(<EmptyState title="No documents yet" description="Upload one." action={<Button>Upload</Button>} />);
    expect(screen.getByRole("heading", { name: "No documents yet" })).toBeTruthy();
    expect(screen.getByText("Upload one.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Upload" })).toBeTruthy();
  });

  it("SectionHeader shows its action and description", () => {
    renderWithIntl(<SectionHeader title="Recent" description="Latest first" action={<a href="/m">All</a>} />);
    expect(screen.getByRole("heading", { name: "Recent" })).toBeTruthy();
    expect(screen.getByText("Latest first")).toBeTruthy();
    expect(screen.getByRole("link", { name: "All" })).toBeTruthy();
  });

  it("Card has a border and no shadow; Divider renders both orientations", () => {
    const { container } = renderWithIntl(
      <>
        <Card data-testid="c">x</Card>
        <Divider />
        <Divider vertical />
      </>,
    );
    const card = screen.getByTestId("c");
    expect(card.className).toContain("border");
    expect(card.className).not.toContain("shadow");
    expect(container.querySelector("hr")).not.toBeNull();
    expect(container.querySelector("[role='separator']")).not.toBeNull();
  });

  it("ListRow draws a left accent only when asked", () => {
    renderWithIntl(
      <ul>
        <ListRow data-testid="plain">a</ListRow>
        <ListRow data-testid="flag" accent="warning">
          b
        </ListRow>
      </ul>,
    );
    expect(screen.getByTestId("plain").className).not.toContain("before:bg-amber");
    expect(screen.getByTestId("flag").className).toContain("before:bg-amber");
  });
});

describe("Menu", () => {
  const onSelect = vi.fn();
  const items = [
    { key: "a", label: "Rename", onSelect },
    { key: "b", label: "Archive", href: "/x" },
  ];

  it("opens on click, moves with arrow keys and closes on Escape, returning focus", () => {
    renderWithIntl(<Menu label="Actions" trigger="Actions" items={items} />);
    const trigger = screen.getByRole("button", { name: "Actions" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const [first, second] = screen.getAllByRole("menuitem") as [HTMLElement, HTMLElement];
    expect(document.activeElement).toBe(first);

    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(document.activeElement).toBe(second);
    fireEvent.keyDown(second, { key: "ArrowDown" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "End" });
    expect(document.activeElement).toBe(second);
    fireEvent.keyDown(second, { key: "Home" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "ArrowUp" });
    expect(document.activeElement).toBe(second);

    fireEvent.keyDown(second, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("runs a button item's action and closes; opens with ArrowDown; closes on outside press or Tab", () => {
    renderWithIntl(<Menu label="Actions" trigger="Actions" items={items} align="right" side="top" />);
    const trigger = screen.getByRole("button", { name: "Actions" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    expect(screen.getByRole("menu")).toBeTruthy();

    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    expect(onSelect).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).toBeNull();

    fireEvent.click(trigger);
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("menu")).toBeNull();

    fireEvent.click(trigger);
    fireEvent.keyDown(screen.getAllByRole("menuitem")[0] as HTMLElement, { key: "Tab" });
    expect(screen.queryByRole("menu")).toBeNull();
  });
});
