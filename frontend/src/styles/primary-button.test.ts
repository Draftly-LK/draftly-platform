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

describe("primary button tokens", () => {
  it("are defined once with the specified values", () => {
    expect(token("primary-top")).toBe("#d6a84d");
    expect(token("primary-bottom")).toBe("#be8d31");
    expect(token("primary-border")).toBe("#a87a26");
    expect(token("primary-hover-top")).toBe("#ddb15a");
    expect(token("primary-hover-bottom")).toBe("#c69436");
    expect(token("primary-pressed")).toBe("#b5862c");
    expect(token("primary-ink")).toBe("var(--navy-950)");
    expect(token("navy-950")).toBe("#0b1628");
    expect(token("primary-highlight")).toBe("inset 0 1px 0 rgb(255 255 255 / 0.35)");
  });

  it("navy ink passes 4.5:1 on every part of the gradient, the lightest and the darkest included", () => {
    const ink = token("navy-950") as string;
    for (const name of ["primary-top", "primary-bottom", "primary-hover-top", "primary-hover-bottom", "primary-pressed"]) {
      expect(contrast(ink, token(name) as string), name).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("the border reads at 3:1 against white, the canvas and both navies, so the button looks the same on each", () => {
    const border = token("primary-border") as string;
    for (const surface of ["#ffffff", "#f3f5f8", "#0f1f38", "#1b3156"]) {
      expect(contrast(border, surface), surface).toBeGreaterThanOrEqual(3);
    }
  });

  it("the Tailwind theme exposes them and no component hard-codes the gold hexes", () => {
    const tailwind = readFileSync(join(__dirname, "../../tailwind.config.ts"), "utf8");
    expect(tailwind).toContain('"primary-gradient": "linear-gradient(to bottom, var(--primary-top), var(--primary-bottom))"');
    expect(tailwind).toContain('"primary-gradient-hover": "linear-gradient(to bottom, var(--primary-hover-top), var(--primary-hover-bottom))"');
    const button = readFileSync(join(__dirname, "../components/ui/button.tsx"), "utf8");
    expect(button).not.toMatch(/#[0-9a-fA-F]{6}/);
  });
});
