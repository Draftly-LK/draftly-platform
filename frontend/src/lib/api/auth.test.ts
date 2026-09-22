import { describe, expect, it } from "vitest";
import { itSendsEach, token, recordFetches } from "@/test/fetch-recorder";
import {
  type ApiUser,
  getAccountStatus,
  getMe,
  needsOnboarding,
  provisionMe,
  updateMe,
} from "./auth";

const recorder = recordFetches();

describe("auth accessors", () => {
  itSendsEach(recorder, [
    {
      name: "provisionMe",
      call: () => provisionMe(token),
      method: "POST",
      path: "/api/v1/me/provision",
    },
    {
      name: "getMe",
      call: () => getMe(token),
      method: "GET",
      path: "/api/v1/me",
    },
    {
      name: "getAccountStatus",
      call: () => getAccountStatus(token),
      method: "GET",
      path: "/api/v1/account-status",
    },
    {
      name: "updateMe",
      call: () =>
        updateMe(token, { phone: null, jurisdiction: "Synthetic division" }),
      method: "PATCH",
      path: "/api/v1/me",
      // null clears a field; it must reach the server, not be dropped.
      body: { phone: null, jurisdiction: "Synthetic division" },
    },
  ]);
});

describe("needsOnboarding", () => {
  const user: ApiUser = {
    id: "usr_synthetic",
    displayName: "Synthetic Notary",
    role: "approver",
    notaryRegistration: "SYN/0001",
    jurisdiction: "Synthetic division",
    qualifications: null,
    professionalTitles: null,
    addressLine1: null,
    addressLine2: null,
    phone: null,
  };

  it("is false once registration and jurisdiction are both set", () => {
    expect(needsOnboarding(user)).toBe(false);
  });

  it.each([
    ["notaryRegistration", null],
    ["notaryRegistration", ""],
    ["jurisdiction", null],
    ["jurisdiction", ""],
  ] as const)("is true when %s is %j", (field, value) => {
    expect(needsOnboarding({ ...user, [field]: value })).toBe(true);
  });

  it("does not ask for the optional fields", () => {
    expect(
      needsOnboarding({ ...user, phone: null, qualifications: null }),
    ).toBe(false);
  });
});
