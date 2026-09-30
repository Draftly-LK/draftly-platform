import { describe, expect, it } from "vitest";
import {
  RTA_REGIME_ID,
  RTA_TAXONOMY,
  allSubtypes,
  conditionalModules,
  families,
  getConditionalModule,
  getSubtype,
  isV0Subtype,
  migrateLegacyMatterType,
  prescribedInstruments,
  familyLabelKey,
  statutoryFamilies,
  subtypeLabelKey,
  subtypesInFamily,
  transactionFamilies,
  v0SubtypeIds,
} from "./taxonomy";

const LEGACY_MATTER_TYPES = ["transfer", "gift", "lease", "mortgage", "other"] as const;

describe("RTA taxonomy contract", () => {
  it("is the RTA regime", () => {
    expect(RTA_REGIME_ID).toBe("lk.rta");
    expect(RTA_TAXONOMY.versions.taxonomy).toBeTruthy();
  });

  it("has exactly 22 prescribed instruments", () => {
    expect(prescribedInstruments()).toHaveLength(22);
  });

  it("gives every subtype a unique id", () => {
    const ids = allSubtypes().map((subtype) => subtype.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("namespaces every subtype id under lk.rta.", () => {
    for (const subtype of allSubtypes()) {
      expect(subtype.id.startsWith("lk.rta.")).toBe(true);
    }
  });

  it("gives every prescribed instrument a gazette form number and a template id", () => {
    for (const instrument of prescribedInstruments()) {
      expect(instrument.gazetteFormNumber).not.toBeNull();
      expect(instrument.gazetteFormNumber).not.toBe("");
      expect(instrument.formTemplateId).not.toBeNull();
      expect(instrument.formTemplateId).not.toBe("");
    }
  });

  it("keeps every subtype inside a known family", () => {
    const familyIds = new Set(families().map((family) => family.id));
    for (const subtype of allSubtypes()) {
      expect(familyIds.has(subtype.familyId)).toBe(true);
    }
  });

  it("orders subtypes deterministically", () => {
    const orders = allSubtypes().map((subtype) => subtype.order);
    expect(orders).toEqual([...orders].sort((a, b) => a - b));
  });
});

describe("form-number collisions", () => {
  // §9.1: a form number alone is never a primary key. Gazette Form 31
  // (register an address) and operational Ti.Re.31 (apply for a new Title
  // Certificate) are both "31" and are different forms.
  it("keeps Gazette Form 31 and operational Ti.Re.31 apart", () => {
    const addressRegister = getSubtype("lk.rta.instrument.address_register");
    const titleCertificate = getSubtype("lk.rta.service.new_title_certificate_application");

    expect(addressRegister?.formTemplateId).toBe("rta.reg.2022.form.31");
    expect(titleCertificate?.formTemplateId).toBe("rta.ops.tire.31");
    expect(addressRegister?.formTemplateId).not.toBe(titleCertificate?.formTemplateId);
  });

  it("lists Ti.Re.31 as a companion template of a transfer on sale", () => {
    const transfer = getSubtype("lk.rta.instrument.transfer_sale");
    expect(transfer?.companionTemplateIds).toContain("rta.ops.tire.31");
  });
});

describe("V0 automation scope", () => {
  it("automates exactly two prescribed instruments", () => {
    const v0Instruments = prescribedInstruments()
      .filter((instrument) => instrument.releaseTier === "V0")
      .map((instrument) => instrument.id);

    expect(v0Instruments.sort()).toEqual([
      "lk.rta.instrument.mortgage_cancel",
      "lk.rta.instrument.transfer_sale",
    ]);
  });

  it("adds the Ti.Re.31 service and nothing else to V0", () => {
    expect([...v0SubtypeIds()].sort()).toEqual([
      "lk.rta.instrument.mortgage_cancel",
      "lk.rta.instrument.transfer_sale",
      "lk.rta.service.new_title_certificate_application",
    ]);
    expect(isV0Subtype("lk.rta.instrument.transfer_sale")).toBe(true);
    expect(isV0Subtype("lk.rta.instrument.gift")).toBe(false);
    expect(isV0Subtype("nonsense")).toBe(false);
  });
});

describe("families", () => {
  it("marks the six transaction families and only those", () => {
    expect(transactionFamilies().map((family) => family.id)).toEqual([
      "ownership_change",
      "agreement_security",
      "use_interest",
      "cancel_release",
      "notice_admin",
      "parcel_structure",
    ]);
  });

  it("keeps title settlement, disputes, and controlled-other out of the transaction list", () => {
    expect(statutoryFamilies().map((family) => family.id)).toEqual([
      "title_settlement",
      "dispute_rectification",
      "controlled_other",
    ]);
  });

  it("returns only that family's subtypes", () => {
    for (const subtype of subtypesInFamily("cancel_release")) {
      expect(subtype.familyId).toBe("cancel_release");
    }
    expect(subtypesInFamily("controlled_other").map((subtype) => subtype.id)).toEqual([
      "lk.rta.instrument.other_declared_instrument",
    ]);
  });
});

describe("conditional modules", () => {
  it("lists only non-empty checklist module id strings", () => {
    expect(conditionalModules().length).toBeGreaterThan(0);
    for (const conditionalModule of conditionalModules()) {
      for (const checklistModuleId of conditionalModule.checklistModuleIds) {
        expect(typeof checklistModuleId).toBe("string");
        expect(checklistModuleId.length).toBeGreaterThan(0);
      }
    }
  });

  // Three modules deliberately add no checklist modules: they change the
  // matter's automation scope or raise an issue rather than extending the
  // checklist. Pinned so an accidental empty list elsewhere is caught.
  it("adds checklist modules for every module except the three scope-only ones", () => {
    const scopeOnly = conditionalModules()
      .filter((conditionalModule) => conditionalModule.checklistModuleIds.length === 0)
      .map((conditionalModule) => conditionalModule.id)
      .sort();

    expect(scopeOnly).toEqual([
      "lk.rta.module.missing_original",
      "lk.rta.module.special_personal_law",
      "lk.rta.module.state_land",
    ]);
  });

  it("looks a module up by id", () => {
    expect(getConditionalModule("lk.rta.module.company_party")?.excludesV0).toBe(true);
    expect(getConditionalModule("lk.rta.module.nope")).toBeUndefined();
  });
});

describe("legacy matter-type migration", () => {
  it("maps every retired M2 matter type onto an existing subtype", () => {
    for (const legacy of LEGACY_MATTER_TYPES) {
      const migration = migrateLegacyMatterType(legacy);
      if (migration === null) throw new Error(`legacy type "${legacy}" is unmapped`);

      const subtype = getSubtype(migration.subtypeId);
      expect(subtype).toBeDefined();
      expect(migration.familyId).toBe(subtype?.familyId);
    }
  });

  it("never migrates without lawyer confirmation", () => {
    for (const legacy of LEGACY_MATTER_TYPES) {
      expect(migrateLegacyMatterType(legacy)?.needsLawyerConfirmation).toBe(true);
    }
  });

  it("returns null rather than guessing for an unmapped value", () => {
    expect(migrateLegacyMatterType("nonsense")).toBeNull();
    expect(migrateLegacyMatterType("")).toBeNull();
  });
});

describe("label keys", () => {
  it("returns the message key for every family and subtype", () => {
    for (const family of families()) {
      expect(familyLabelKey(family.id)).toBe(family.labelKey);
    }
    for (const subtype of allSubtypes()) {
      expect(subtypeLabelKey(subtype.id)).toBe(subtype.labelKey);
    }
  });

  it("returns undefined for an unknown id rather than guessing", () => {
    // @ts-expect-error deliberately outside the typed id union
    expect(familyLabelKey("no_such_family")).toBeUndefined();
    expect(subtypeLabelKey("no_such_subtype")).toBeUndefined();
  });
});
