import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import en from "./messages/en.json";
import si from "./messages/si.json";

/**
 * Every value of a backend enum that the UI shows must have a label.
 *
 * The OpenAPI contract types these fields as plain `string`, so nothing else
 * catches a value the frontend has no message for — it reaches the screen as
 * `gazette.unresolvedReason.NO_FACT`. The Python enum is the source of truth, so
 * this reads it. When a backend enum gains a value, this fails until the
 * catalogue does too (and `humanize.ts` covers the gap in the meantime).
 */
const BACKEND = fileURLToPath(new URL("../../../../backend/src/modules/", import.meta.url));

interface Parity {
  file: string;
  enumName: string;
  /** Catalogue group that must contain a label for every value. */
  group: string;
}

const PARITY: Parity[] = [
  { file: "content_governance/domain/enums.py", enumName: "UnresolvedReason", group: "gazette.unresolvedReason" },
  { file: "content_governance/domain/enums.py", enumName: "MatterState", group: "matterNav.stateLabel" },
  { file: "content_governance/domain/enums.py", enumName: "GeneratedFormState", group: "generatedFormState" },
  { file: "content_governance/domain/enums.py", enumName: "SourceFileState", group: "enums.sourceFileState" },
  { file: "content_governance/domain/enums.py", enumName: "FactStatus", group: "enums.factStatus" },
  { file: "content_governance/domain/enums.py", enumName: "IssueSeverity", group: "checks.severity" },
  { file: "content_governance/domain/enums.py", enumName: "IssueState", group: "checks.state" },
  { file: "content_governance/domain/enums.py", enumName: "BlockerKind", group: "checks.blocker" },
  { file: "draft/domain/policies.py", enumName: "PreflightCode", group: "enums.preflightCode" },
];

function enumValues(source: string, enumName: string): string[] {
  const start = source.indexOf(`class ${enumName}(`);
  if (start === -1) return [];
  const rest = source.slice(start).split("\n").slice(1);
  const values: string[] = [];
  for (const line of rest) {
    if (/^\S/.test(line)) break; // next top-level statement ends the class body
    const match = /^\s+[A-Z][A-Z0-9_]*\s*=\s*"([^"]+)"/.exec(line);
    if (match) values.push(match[1]!);
  }
  return values;
}

function group(catalogue: unknown, path: string): Record<string, unknown> | undefined {
  let node: unknown = catalogue;
  for (const part of path.split(".")) {
    if (typeof node !== "object" || node === null) return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "object" && node !== null ? (node as Record<string, unknown>) : undefined;
}

describe.skipIf(!existsSync(BACKEND))("backend enums have labels in both catalogues", () => {
  for (const { file, enumName, group: path } of PARITY) {
    it(`${enumName} → ${path}`, () => {
      const values = enumValues(readFileSync(`${BACKEND}${file}`, "utf8"), enumName);
      expect(values.length, `could not read ${enumName} from ${file}`).toBeGreaterThan(0);
      for (const [name, catalogue] of [["en", en], ["si", si]] as const) {
        const labels = group(catalogue, path);
        const missing = values.filter((value) => typeof labels?.[value] !== "string");
        expect(missing, `${path} (${name}) has no label for`).toEqual([]);
      }
    });
  }
});
