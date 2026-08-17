import { describe, expect, it } from "vitest";
import { diffProfile, toEditableProfile, type EditableProfile } from "./profile-fields";

const BLANK: EditableProfile = {
  displayName: "",
  professionalTitles: "",
  qualifications: "",
  notaryRegistration: "",
  jurisdiction: "",
  addressLine1: "",
  addressLine2: "",
  phone: "",
};

describe("diffProfile", () => {
  it("returns nothing when no field changed", () => {
    const saved: EditableProfile = { ...BLANK, phone: "011 234 5678" };
    expect(diffProfile(saved, { ...saved })).toEqual({});
  });

  it("sends only the fields that actually changed", () => {
    const saved: EditableProfile = { ...BLANK, jurisdiction: "Colombo", phone: "011 234 5678" };
    expect(diffProfile(saved, { ...saved, jurisdiction: "Gampaha" })).toEqual({
      jurisdiction: "Gampaha",
    });
  });

  it("clears a previously set field with an explicit null, so a value can be removed", () => {
    const saved: EditableProfile = { ...BLANK, addressLine2: "Nugegoda" };
    expect(diffProfile(saved, { ...saved, addressLine2: "" })).toEqual({ addressLine2: null });
  });

  it("omits a field that was blank and stayed blank rather than clearing it", () => {
    expect(diffProfile(BLANK, { ...BLANK, addressLine2: "   " })).toEqual({});
  });

  it("trims what it sends, and treats a whitespace-only edit of a set field as a clear", () => {
    const saved: EditableProfile = { ...BLANK, qualifications: "Attorney-at-Law" };
    expect(diffProfile(saved, { ...saved, qualifications: "  Notary Public  " })).toEqual({
      qualifications: "Notary Public",
    });
    expect(diffProfile(saved, { ...saved, qualifications: "   " })).toEqual({
      qualifications: null,
    });
  });

  it("ignores a change that only adds surrounding whitespace", () => {
    const saved: EditableProfile = { ...BLANK, notaryRegistration: "NR-4821" };
    expect(diffProfile(saved, { ...saved, notaryRegistration: "  NR-4821 " })).toEqual({});
  });
});

describe("toEditableProfile", () => {
  it("coerces the wire user's nulls to empty strings", () => {
    expect(
      toEditableProfile({
        displayName: "W. A. Perera",
        professionalTitles: null,
        qualifications: null,
        notaryRegistration: "NR-4821",
        jurisdiction: "Colombo",
        addressLine1: null,
        addressLine2: null,
        phone: null,
      }),
    ).toEqual({
      ...BLANK,
      displayName: "W. A. Perera",
      notaryRegistration: "NR-4821",
      jurisdiction: "Colombo",
    });
  });
});
