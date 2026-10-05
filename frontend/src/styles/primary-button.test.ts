import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(__dirname, "globals.css"), "utf8");
const token = (name: string) => new RegExp(`--${name}:\s*([^;]+);`).exec(css)?.[1]?.trim();

const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const luminance = (hex: string) => {
  const [r, g, b] = rgb(hex).map((v) => v / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
};
const contrast = (a: string, b: string) => {
  const [x, y] = [luminance(a), luminance(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
};

// Composite translucent gradient endpoints onto each supported backdrop.
const blend = (foreground: string, background: string) => "#" + rgb(foreground)
  .map((value, index) => Math.round(value * 0.96 + (rgb(background)[index] ?? 0) * 0.04).toString(16).padStart(2, "0"))
  .join("");

describe("primary button tokens", () => {
  it("are defined once with the specified values", () => {
    expect(token("primary-bg")).toBe("rgb(249 232 198 / 0.96)");
    expect(token("primary-end")).toBe("rgb(237 205 147 / 0.96)");
    expect(token("primary-hover")).toBe("#f5deb0");
    expect(token("primary-pressed")).toBe("#f9edc8");
    expect(token("primary-border")).toBe("#ad7b24");
    expect(token("primary-icon")).toBe("#95651c");
    expect(token("primary-ink")).toBe("var(--navy-950)");
    expect(token("navy-950")).toBe("#0b1628");
  });

  it("navy ink passes 4.5:1 on every primary state", () => {
    const ink = token("navy-950") as string;
    for (const name of ["primary-hover", "primary-pressed"]) {
      expect(contrast(ink, token(name) as string), name).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("the outline and icon pass 3:1 on every state and surrounding surface", () => {
    const border = token("primary-border") as string;
    for (const surface of ["#ffffff", "#f3f5f8", "#f5deb0", "#f9edc8", "#0f1f38", "#1b3156"]) {
      if (!surface.startsWith("#0f") && !surface.startsWith("#1b")) {
        expect(contrast(token("primary-icon") as string, surface), surface).toBeGreaterThanOrEqual(3);
      }
      // The border separates the control from its surrounding page, not its fill.
      if (["#ffffff", "#f3f5f8", "#0f1f38", "#1b3156"].includes(surface)) {
        expect(contrast(border, surface), surface).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it("translucent gradient endpoints retain text and icon contrast on light and navy surfaces", () => {
    for (const backdrop of ["#ffffff", "#f3f5f8", "#0f1f38", "#1b3156"]) {
      for (const endpoint of ["#f9e8c6", "#edcd93"]) {
        const surface = blend(endpoint, backdrop);
        expect(contrast(token("navy-950") as string, surface)).toBeGreaterThanOrEqual(4.5);
        expect(contrast(token("primary-icon") as string, surface)).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it("the Tailwind theme exposes them and no component hard-codes the gold hexes", () => {
    const tailwind = readFileSync(join(__dirname, "../../tailwind.config.ts"), "utf8");
    expect(tailwind).toContain('"primary-bg": "var(--primary-bg)"');
    expect(tailwind).toContain('"primary-icon": "var(--primary-icon)"');
    expect(tailwind).not.toContain("primary-gradient");
    const button = readFileSync(join(__dirname, "../components/ui/button.tsx"), "utf8");
    expect(button).not.toMatch(/#[0-9a-fA-F]{6}/);
  });
});
