// @vitest-environment happy-dom
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import en from "@/lib/i18n/messages/en.json";
import si from "@/lib/i18n/messages/si.json";
import { renderWithIntl } from "@/test/render";
import { RegisterError } from "./fact-register-common";

describe("fact decision refusal guidance", () => {
  it.each([
    [
      401,
      "identity_validation_failed",
      "sessionExpired",
      "signInAgain",
      "/sign-in",
    ],
    [
      403,
      "practice_status_required",
      "practiceRequired",
      "reviewProfile",
      "/profile",
    ],
  ] as const)(
    "gives the next action for %s %s",
    (status, code, message, action, href) => {
      renderWithIntl(
        <RegisterError
          cause={new ApiError(status, code, "Synthetic refusal", "", {})}
        />,
      );

      const alert = within(screen.getByRole("alert"));
      expect(alert.getByText(en.factRegister[message])).toBeTruthy();
      expect(
        alert
          .getByRole("link", { name: en.factRegister[action] })
          .getAttribute("href"),
      ).toBe(href);
    },
  );

  it("directs capability refusals to an administrator without a profile link", () => {
    renderWithIntl(
      <RegisterError
        cause={
          new ApiError(403, "capability_denied", "Synthetic refusal", "", {})
        }
      />,
    );

    expect(screen.getByText(en.factRegister.capabilityRequired)).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("does not describe an unknown access refusal as a practising-status problem", () => {
    renderWithIntl(
      <RegisterError
        cause={
          new ApiError(403, "unknown_refusal", "Synthetic refusal", "", {})
        }
      />,
    );

    expect(screen.getByText(en.factRegister.permissionRefused)).toBeTruthy();
    expect(screen.queryByText(en.factRegister.practiceRequired)).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("translates practising-status guidance and its profile action into Sinhala", () => {
    renderWithIntl(
      <RegisterError
        cause={
          new ApiError(
            403,
            "practice_status_required",
            "Synthetic refusal",
            "",
            {},
          )
        }
      />,
      "si",
    );

    expect(screen.getByText(si.factRegister.practiceRequired)).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: si.factRegister.reviewProfile })
        .getAttribute("href"),
    ).toBe("/profile");
  });

  it.each([
    [404, "recordUnavailable", false],
    [409, "decisionRefused", true],
    [422, "decisionRefused", true],
    [503, "apiUnavailable", false],
  ] as const)(
    "preserves existing guidance for status %s",
    (status, message, showDetail) => {
      renderWithIntl(
        <RegisterError
          cause={
            new ApiError(status, "synthetic_error", "Synthetic refusal", "", {})
          }
        />,
      );

      expect(screen.getByText(en.factRegister[message])).toBeTruthy();
      expect(Boolean(screen.queryByText("Synthetic refusal"))).toBe(showDetail);
      expect(screen.queryByRole("link")).toBeNull();
    },
  );
});
