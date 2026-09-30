import type { JSONContent } from "@tiptap/core";
import { doc, item, line, signatures, slot, table } from "../builders";
import {
  SIGNATURE_DOTS,
  attestation,
  fees,
  formHeader,
  landDetails,
  officeUseBox,
  party,
  priorRegistration,
  witnessTable,
} from "./shared";

/*
 * Form 12 — Instrument of Cancellation of a Mortgage (RTA s. 43).
 * Source: Gazette Extraordinary 1886/58 of 2014.10.31, pages 13A–14A.
 * Transcription: docs/reference/forms/transcriptions/si/form-12.txt.
 *
 * Wording is verbatim, including "ලේඛණයේ" and "ගැණුම්කරු" as printed, and
 * the release clause naming the mortgagor ("උකස් දීමනාකරු") as the releasing
 * party. None of it is corrected here: legal wording is human-owned, and this
 * template is an unapproved transcription.
 */

const P = "f12";

export const form12Document: JSONContent = doc([
  ...formHeader("12", "උකස අවලංගු කිරීමේ සාධන පත්‍රය"),
  officeUseBox({ receipt: "බැංකු ලදුපත් අංකය", certificateColon: false }),
  landDetails(
    P,
    {
      a: "district",
      aa: "ds_division",
      ae: "gn_division",
      u: "cadastral_map_no",
      uu: "block_no",
      e: "parcel_no",
      ee: "extent",
    },
    [
      line("entry", ["(ඔ) උකසට යටත්වන ඉඩමේ ප්‍රමාණය : ", slot(`${P}.1.o`)]),
      line("entry", ["(ඕ) සහාධිපත්‍ය දේපලක් නම් ඒකකයේ අංකය : ", slot(`${P}.1.oo`)]),
    ],
  ),
  priorRegistration(P, { a: "place_of_registration", aa: "title_certificate_no", ae: "class_of_title" }),
  party(P, "3.", "උකස් දීමනාකරු :", { name: "registered_owner_name" }),
  party(P, "4.", "උකස් ගැනුම්කරු :", { name: "mortgagee_name", address: "mortgagee_address" }),
  item("5.", [
    line("itemTitle", ["උකස් කිරීමේ සාධන පත්‍රය :"]),
    table(
      [["දිනපොත් අංකය"], ["දිනය"], ["මුල් මුදල"], ["සහතික කළ තැනැත්තා"]],
      [
        [
          [slot(`${P}.5.day_book`, { field: "mortgage_reference", labelKey: "mortgageDayBook" })],
          [slot(`${P}.5.date`, { field: "mortgage_registration_date", labelKey: "mortgageDate" })],
          [slot(`${P}.5.principal`, { labelKey: "mortgagePrincipal" })],
          [slot(`${P}.5.attested_by`, { multiline: true, labelKey: "mortgageAttestedBy" })],
        ],
      ],
    ),
  ]),
  fees(P, "6.", "බැංකු ලදුපත් අංකය"),
  line(
    "para",
    [
      slot(`${P}.release.mortgagor_address`, { size: "md", labelKey: "releaseMortgagorAddress" }),
      " පදිංචි ",
      slot(`${P}.release.mortgagor_name`, { size: "md", labelKey: "releaseMortgagorName" }),
      " (උකස් දීමනාකරුට) අයත් ඉඩමට අදාළ ඉහත සඳහන් උකස සම්බන්ධයෙන් වූ මුල් මුදල, පොලියද ගෙවා අවසන් බැවින් එම ඉඩම ",
      slot(`${P}.release.releasor_address`, { size: "lg", labelKey: "releaseReleasorAddress" }),
      " පදිංචි ",
      slot(`${P}.release.releasor_name`, { size: "lg", labelKey: "releaseReleasorName" }),
      " (උකස් දීමනාකරු) වන මම මෙයින් නිදහස් කරමි. මෙම උකස අවලංගු කිරීම හිමිකම් ලේඛණයේ ලියාපදිංචි කරන මෙන් ඉල්ලමි.",
    ],
    { indent: true, space: true },
  ),
  signatures([
    line("signature", [SIGNATURE_DOTS], { space: true }),
    line("signature", [SIGNATURE_DOTS], { space: true }),
    line("signature", ["අයිතිකරුගේ අත්සන"], { align: "center" }),
    line("signature", ["උකස් ගැනුම්කරුගේ අත්සන"], { align: "center" }),
    line("signature", ["දිනය : ", slot(`${P}.sign.owner_date`, { labelKey: "ownerSignedOn" })], {
      space: true,
    }),
    line("signature", ["දිනය : ", slot(`${P}.sign.mortgagee_date`, { labelKey: "mortgageeSignedOn" })], {
      space: true,
    }),
  ]),
  line(
    "para",
    [
      "7. සාක්ෂිකරුවන්ගේ ප්‍රකාශය : මෙම උකස් අවලංගු කිරීමේ සාධන පත්‍රය ",
      slot(`${P}.7.date`, { size: "sm", labelKey: "witnessedOn" }),
      " දින අප ඉදිරියේ ",
      slot(`${P}.7.place`, { size: "md", labelKey: "witnessedAt" }),
      " දී අත්සන් කරන ලද බවත්, උකස් දීමනාකරු හා උකස් ගැණුම්කරු අප හොඳින් දන්නා හඳුනන අය බවත්, අප මෙයින් සහතික කරමු.",
    ],
    { indent: true, space: true },
  ),
  witnessTable(P),
  ...attestation(P, { date: "attestation_date" }),
]);
