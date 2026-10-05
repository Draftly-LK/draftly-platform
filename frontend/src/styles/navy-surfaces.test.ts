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
  it("every navy surface uses the one inverse-surface token, so they meet without a seam", () => {
    const offenders = files.filter((file) => /\bbg-navy-(800|900|950)\b/.test(readFileSync(file, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("the sidebar, dashboard header and sign-in panel all use that token", () => {
    for (const rel of ["components/shell/sidebar.tsx", "components/home/dashboard.tsx", "components/auth/auth-shell.tsx"]) {
      expect(readFileSync(join(SRC, rel), "utf8"), rel).toContain("bg-surface-inverse");
    }
  });

  it("the sidebar has no border or gradient on its edge", () => {
    const sidebar = readFileSync(join(SRC, "components/shell/sidebar.tsx"), "utf8");
    const aside = sidebar.slice(sidebar.indexOf("<aside"), sidebar.indexOf(">", sidebar.indexOf("<aside")));
    expect(aside).not.toMatch(/\bborder-r\b|\bborder-white\b|gradient/);
  });

  it("the token resolves to #0F1F38", () => {
    const css = readFileSync(join(SRC, "styles/globals.css"), "utf8");
    expect(css).toMatch(/--navy-900:\s*#0f1f38/i);
    expect(css).toMatch(/--surface-inverse:\s*var\(--navy-900\)/);
  });
});
