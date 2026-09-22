import { describe, expect, it } from "vitest";
import { allSubtypes, families, isV0Subtype } from "./taxonomy";
import {
  availableRtaWorkflowCount,
  commonRtaWorkflows,
  rtaWorkflows,
  rtaWorkflowsByFamily,
} from "./workflow-catalogue";

describe("rtaWorkflows", () => {
  it("has one workflow per subtype, in taxonomy order", () => {
    expect(rtaWorkflows().map((w) => w.subtype.id)).toEqual(allSubtypes().map((s) => s.id));
  });

  it("pairs each workflow with its own family", () => {
    for (const workflow of rtaWorkflows()) {
      expect(workflow.family.id).toBe(workflow.subtype.familyId);
    }
  });

  it("marks available exactly the subtypes this release prepares", () => {
    for (const workflow of rtaWorkflows()) {
      expect(workflow.available).toBe(isV0Subtype(workflow.subtype.id));
    }
  });
});

describe("rtaWorkflowsByFamily", () => {
  it("keeps family order and drops empty families", () => {
    const groups = rtaWorkflowsByFamily();
    const familyOrder = families().map((f) => f.id);

    const positions = groups.map((group) => familyOrder.indexOf(group.family.id));
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
    expect(groups.every((group) => group.workflows.length > 0)).toBe(true);
  });

  it("puts each workflow under its family, and loses none", () => {
    const groups = rtaWorkflowsByFamily();

    for (const group of groups) {
      expect(group.workflows.every((w) => w.subtype.familyId === group.family.id)).toBe(true);
    }
    const grouped = groups.flatMap((group) => group.workflows.map((w) => w.subtype.id));
    expect(new Set(grouped)).toEqual(new Set(rtaWorkflows().map((w) => w.subtype.id)));
  });
});

describe("commonRtaWorkflows", () => {
  it("starts with the sale transfer, the release's core instrument", () => {
    expect(commonRtaWorkflows()[0]?.subtype.id).toBe("lk.rta.instrument.transfer_sale");
  });

  it.each([
    [0, 0],
    [1, 1],
    [3, 3],
  ])("a limit of %i gives %i workflows", (limit, expected) => {
    expect(commonRtaWorkflows(limit)).toHaveLength(expected);
  });

  it("a limit past the list gives the whole list, no more", () => {
    expect(commonRtaWorkflows(1000)).toEqual(commonRtaWorkflows());
  });

  it("lists only subtypes that exist, each once", () => {
    const known = new Set(allSubtypes().map((s) => s.id));
    const ids = commonRtaWorkflows().map((w) => w.subtype.id);

    expect(ids.every((id) => known.has(id))).toBe(true);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("availableRtaWorkflowCount", () => {
  it("counts the release's subtypes, and at least the sale transfer", () => {
    const count = availableRtaWorkflowCount();

    expect(count).toBe(allSubtypes().filter((s) => isV0Subtype(s.id)).length);
    expect(count).toBeGreaterThanOrEqual(1);
  });
});
