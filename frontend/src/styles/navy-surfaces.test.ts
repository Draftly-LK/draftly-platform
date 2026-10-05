import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "node_modules" ? [] : sourceFiles(path);
    return /\.tsx$/.test(entry.name) && !/\.test\./.test(entry.name) ? [path] : [];
  });
}

const files = [...sourceFiles(join(SRC, "components")), ...sourceFiles(join(SRC, "app"))];

describe("navy surfaces", () => {
  it("every navy surface uses the one inverse-surface token as its base colour", () => {
    const offenders = files.filter((file) => /\bbg-navy-(800|900|950)\b/.test(readFileSync(file, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("the sidebar, dashboard header and sign-in panel all use that token", () => {
    for (const rel of ["components/shell/sidebar.tsx", "components/home/dashboard.tsx", "components/auth/auth-shell.tsx"]) {
      expect(readFileSync(join(SRC, rel), "utf8"), rel).toContain("bg-surface-inverse");
    }
  });

  it("the sidebar and the dashboard header draw the same backdrop; the sign-in panel has its own", () => {
    for (const rel of ["components/shell/sidebar.tsx", "components/home/dashboard.tsx", "components/auth/auth-shell.tsx"]) {
      expect(readFileSync(join(SRC, rel), "utf8"), rel).toContain("<NavyBackdrop");
    }
  });

  it("the sidebar has a 1px edge at 8% white and the soft sidebar shadow, and nothing else on the edge", () => {
    const sidebar = readFileSync(join(SRC, "components/shell/sidebar.tsx"), "utf8");
    const aside = sidebar.slice(sidebar.indexOf("<aside"), sidebar.indexOf(">", sidebar.indexOf("<aside")));
    expect(aside).toContain("border-r border-white/[0.08]");
    expect(aside).toContain("shadow-sidebar");
    expect(aside).not.toMatch(/gradient/);
  });

  it("the token resolves to #0F1F38", () => {
    const css = readFileSync(join(SRC, "styles/globals.css"), "utf8");
    expect(css).toMatch(/--navy-900:\s*#0f1f38/i);
    expect(css).toMatch(/--surface-inverse:\s*var\(--navy-900\)/);
  });
});

describe("navy backdrop", () => {
  const source = readFileSync(join(SRC, "components/shell/navy-backdrop.tsx"), "utf8");

  it("is one SVG that covers its area and is never tiled", () => {
    expect(source).toContain('preserveAspectRatio="xMidYMid slice"');
    // Code, not the comment that explains why: no <pattern> and no CSS repeat.
    expect(source).not.toMatch(/<pattern|backgroundRepeat|background-repeat/);
  });

  it("uses the specified gradient: #1B3156 at the top-left, then #0F1F38, then #0B1628", () => {
    const stops = [...source.matchAll(/stopColor="(#[0-9A-Fa-f]{6})"/g)].map((m) => m[1]);
    expect(stops).toEqual(["#1B3156", "#0F1F38", "#0B1628"]);
  });

  it("draws the parcel lines white, 1px, at 7% opacity, kept 1px when scaled", () => {
    expect(source).toMatch(/stroke="#fff"[^>]*strokeOpacity="0\.07"[^>]*strokeWidth="1"/);
    expect(source).toContain('vectorEffect="non-scaling-stroke"');
  });

  it("is irregular: many straight segments of differing lengths, not a grid", () => {
    const path = /const PARCELS =\s*"([^"]+)"/.exec(source)?.[1] ?? "";
    const segments = [...path.matchAll(/M([\d.]+) ([\d.]+)L([\d.]+) ([\d.]+)/g)].map(([, x1, y1, x2, y2]) =>
      Math.hypot(Number(x2) - Number(x1), Number(y2) - Number(y1)),
    );
    expect(segments.length).toBeGreaterThan(150);
    const lengths = new Set(segments.map((l) => Math.round(l / 10)));
    expect(lengths.size).toBeGreaterThan(20);
  });

  it("is hidden from assistive tech and cannot take clicks", () => {
    expect(source).toContain('aria-hidden="true"');
    expect(source).toContain("pointer-events-none");
  });
});
