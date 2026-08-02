# RTA Materials — Extraction Report (Draftly repo)

> Research extract from gazette form pages `page-28.png`–`page-48.png`
> (Registration of Title Act prescribed forms). Recovered from git history
> when the images were missing from the working tree. Printed page content
> is authoritative over `manifest.json` labels.

## 0. Critical sourcing note (read first)

The PNG pages **do not exist in the current working tree**.
`docs/reference/forms/` is absent on the checked-out branch (HEAD `ff2c3af`).
The images were added in commit **`64d0725` — `feat(e7-2): add Tiptap
statutory form templates`** and later removed. They were recovered from that
commit via git for this extract, then discarded. The full set in that commit
is `page-01.png` … `page-48.png` plus `manifest.json` and the source PDF
`docs/reference/1886-58_S.pdf`.

**Source document:** The pages are from **Sri Lanka Gazette Extraordinary No. 1886/58, dated 2014.10.31** (`I කොටස : (I) ඡේදය` — Part I §I). Every form is headed *"1998 අංක 21 දරන හිමිකම් ලියාපදිංචි කිරීමේ පනත"* = the **Registration of Title Act, No. 21 of 1998**. So these are the **prescribed statutory forms** ("ආකෘති පත්‍ර") under the RTA, in Sinhala.

**Manifest reliability warning:** `manifest.json` is a team-authored index. Its
`titleEn` labels are **wrong for several forms** when checked against the
printed pages, and its `pdfPages` numbering does **not** line up with the
`page-NN.png` gazette page numbers. Treat the **printed page content as
authoritative**; each mismatch is flagged below.

---

## 1. Inventory of every page read (page-28 → page-48)

Each transaction form is a two-page spread: a front page (office-use box + land/party details) and a back page (declaration, signatures, witnesses, notary attestation). Forms are identified by the printed *"ආකෘති පත්‍ර අංක - NN"* (Form No.) and the cited section (*"වගන්තිය"*).

- **page-28** — Tail of the **Relinquishment/Cancellation of Life Interest** form. Shows items 6–8: reason for cancellation, fees (registration fee + stamp duty with receipt numbers), a declaration to register cancellation of the life interest in the title register, signatures of the *life-interest holder* (ජීවිත භුක්තිය හිමිකරු) and the *owner* (අයිතිකරු), a witness table (full name / NIC / address / signature) and the notary attestation block. Footnote cites **s.44** of the RTA.
- **page-29** — Front page of **Form No. 26 — "විකුණුම් ගිවිසුම අවලංගු කිරීමේ සාධන පත්‍රය" = Instrument of Cancellation of the Agreement to Sell** (cites **s.43**). Office-use registration box, then item 1 land details (district, DS division, GN division, street/village, valuation no., cadastral map no., block/parcel no., extent), item 2 prior registration, item 3 agreement period, item 4 effective date, item 5 seller details.
- **page-30** — Back page of **Form 26**. Items 6–11: buyer details, gross/net consideration, reason and date of cancellation, fees, cancellation declaration, signatures of *buyer* (ගැනුම්කරු) and *grantor* (දීමනාකරු), item 12 witnesses table + notary attestation. Footnote **s.44**.
- **page-31** — Front page of **Form No. 21 — "සහාධිපත්‍ය දේපලක් බවට පත් කිරීමේ සාධන පත්‍රය" = Instrument to Convert Property into a Condominium/Common-hold** (cites **s.50**). Notes it applies to buildings (ගොඩනැගිල්ල). Applicant name, NIC, address; land details; nature of condominium property (temporary / permanent / common —
තාවකාලික / ස්ථිර / සාමාන්‍ය).
- **page-32** — Back of **Form 21** (items 8–11: condominium plan details — surveyor name, plan no., date, cadastral map no.; fees; a declaration referencing the **Apartment Ownership Law No. 11 of 1973 as amended by Act No. … of 2003**; applicant signature). **Then** the front of **Form No. 25 — "විකුණුම් සහතිකය ලියාපදිංචි කිරීමේ සාධන පත්‍රය" = Instrument for Registration of a Certificate of Sale** begins (cites **s.43**), with its office-use box.
- **page-33** — Body of **Form 25** (Certificate of Sale). Items 1–8: land details, prior registration, original undertaking/decree, value of the certificate of sale, *authorized auctioneer* (බලලත් වෙන්දේසිකරු), *creditor/mortgagee* (ණය හිමිකරු/දීමනාකරු), *purchaser* (ගැනුම්කරු), fees. Signed by the auctioneer and the creditor/original institution. Page footer `3 — PG 2227`.
- **page-34** — Tail of **Form 25**: item 9 witnesses table + notary attestation. Footnote **s.44**.
- **page-35** — **Form No. 14 — "හිමිකම් සහතිකය" = Certificate of Title** (cites **s.37**), bearing the national emblem. Header fields: folio, province, district, DS division, GN division, name, address; cadastral map no., block no., parcel no., land use, extent, land nature. **First Schedule (පළමුවන උපලේඛනය) = Proprietorship** (owner name, address, NIC). **Second Schedule (දෙවන උපලේඛනය) = Plan of Land**, flanked by two heraldic lion images. Registrar of Title signature; notes cite **s.65**. This is the physical title certificate issued to the owner.
- **page-36** — Landscape (rotated) continuation table for the Certificate of Title — the **encumbrances/register schedule**: prior registration, notary name, encumbrance details, registered date, cancelled date, remarks (වෙනත් කරුණු).
- **page-37** — **Form No. 14(අ) [14A] — "හිමිකම් සහතිකය" = Certificate of Title (variant A)** (cites **s.37**), same emblem and structure as Form 14 (First Schedule ownership, Second Schedule plan with lions, Registrar signature).
- **page-38** — Top: **Third Schedule (තුන්වැනි උපලේඛනය)** table for the Form 14(A) title certificate (encumbrance ledger: nature, number & date, notary name, details, registered date/receipt/receiving officer, cancelled date/receipt/officer). Bottom: **Form No. 19 — "හිමිකම් රෙජිස්ටරය" = the Title Register (folio)** begins. Item 1 "land part" (ඉඩම සම්බන්ධ අංශය): district, DS, GN, street/village, valuation no., cadastral map no., block/parcel no., extent + title number.
- **page-39** — Body of **Form 19** (Title Register). Item 2 = **First Schedule** (ownership register: owner full name/address/NIC, document nature & number, extent/share, related ownership, nature & title-class, registration date/time, Registrar signature, remarks). **Second Schedule** = charges/encumbrances (බැඳීම්). Item 3, **Third Schedule**, Item 4 "other details": (1) dues owed to State/local authority, (2) natural resources or improvements on the land, (3) other remarks, (4) cross-notes. Registrar of Title.
- **page-40** — **Form No. 19(අ) [19A] — "හිමිකම් රෙජිස්ටරය" = Title Register (State-land variant)**. Item 1 land part; **First Schedule = "අයිතිය - රජයේ" (Ownership — State)** with a table for control/administration details (document no., registration date/time, controlling officer/agency name & address, ministry no., institution, nature, division, variation no., remarks on rights created).
- **page-41** — Continuation of **Form 19(A)**: **Second Schedule** = charges (බැඳීම්) ledger; **Third Schedule**; Item 4 "other details": (1) State/local-authority dues, (2) improvements, (3) other. Signed by **Registrar of Lands (ඉඩම් රෙජිස්ට්‍රාර්)**.
- **page-42** — Front of **Form No. 32 — "ඉඩමක් හුවමාරු කිරීමේ සාධන පත්‍රය" = Instrument of Exchange of Land** (cites **s.43**). Two office-use boxes (one per land parcel: "පළුමුවන ඉඩම් කොටස" / "දෙවන ඉඩම් කොටස"). Item 1 = parallel land details for **both** parcels being exchanged.
- **page-43** — Body of **Form 32** (Exchange). Item 2 prior registration, item 3 first party, item 4 second party, item 5 consideration (value of first land / second land), item 6 fees, item 7 conditions, exchange declaration, signatures of first and second party, item 8 witnesses table.
- **page-44** — Top: tail of **Form 32** (notary attestation, **s.44** footnote). Bottom: front of **Form No. 24 — "ඇපයක් වෙනුවෙන් පවරන ලද සාධන පත්‍රය" = Instrument of Transfer Given as Security/Surety** (cites **s.43**). Office-use box; item 1 land details; item 2 prior registration.
- **page-45** — Body of **Form 24** (transfer as security). Item 3 transferor/pledgor (ඇපකරු), item 4 the institution holding the security (name, registration no., registered address — a bank/full business/trading entity), item 5 duration the security remains valid, item 6 property value, item 7 fees, item 8 conditions, item 9 encumbrances table. Declaration that the property is transferred as security for a debt; signatures of *pledgor* (ඇපකරු) and *security-taker* (ඇප ගැනුම්කරු). Item 10 witnesses.
- **page-46** — Top: tail of **Form 24** — item 11 = **release/cancellation of the security bond** (ඇප බැඳුමකරය අවලංගු කිරීම), signed by the security-taker; **s.44** notary footnote. Bottom: front of **Form No. 27 — "න්‍යාසය අවලංගු කිරීමේ සාධන පත්‍රය" = Instrument of Cancellation of a Trust (න්‍යාසය)** (cites **s.43**). Office-use box; item 1 land details incl. extent of land under the trust being cancelled.
- **page-47** — Body of **Form 27** (cancellation of trust). Item 2 prior registration, item 3 settlor/trustor (න්‍යාසාදායක), item 4 the party to whom cancellation is granted, item 5 conditions in the trust instrument, item 6 details of the trust deed being cancelled (number, notary name, date), item 7 fees, item 8 grounds/conditions for cancellation, item 9 encumbrances. Declaration references a **life-interest holder (ජීවිත භුක්ති හිමිකරු)**; signed by settlor and life-interest holder. *(This form's item-4/declaration text mixes trust, gift and life-interest wording — see §6 Ambiguities.)*
- **page-48** — Top: tail of **Form 27** (item 10 witnesses + notary attestation, **s.44** footnote). Bottom: **the fee schedule — "දෙවන උපලේඛනය" (Second Schedule)** with two tables: **Application Fees (ඉල්ලුම්පත්‍ර ගාස්තු)** and **Registration Fees (ලියාපදිංචි කිරීමේ ගාස්තු)** — transcribed in §5. Footer `11 - 407`; printed by the Sri Lanka Government Press.

---

## 2. Master list of transaction types / forms

### A. Verified from the printed pages 28–48 (authoritative)

| Form No. (printed) | Sinhala title | Transaction (English) | Act section cited |
|---|---|---|---|
| — (tail on p28) | ජීවිත භුක්තිය අවලංගු කිරීම | Relinquishment/Cancellation of **Life Interest** | s.44 (attest.) |
| **26** | විකුණුම් ගිවිසුම අවලංගු කිරීමේ සාධන පත්‍රය | **Cancellation of an Agreement to Sell** | s.43 |
| **21** | සහාධිපත්‍ය දේපලක් බවට පත් කිරීමේ සාධන පත්‍රය | Conversion of property into a **Condominium** | s.50 |
| **25** | විකුණුම් සහතිකය ලියාපදිංචි කිරීමේ සාධන පත්‍රය | Registration of a **Certificate of Sale** | s.43 |
| **14** | හිමිකම් සහතිකය | **Certificate of Title** (owner's certificate) | s.37 (notes s.65) |
| **14(අ)/14A** | හිමිකම් සහතිකය | **Certificate of Title (variant A)** | s.37 |
| **19** | හිමිකම් රෙජිස්ටරය | **Title Register / folio** (private land) | — |
| **19(අ)/19A** | හිමිකම් රෙජිස්ටරය (රජයේ) | **Title Register — State land** variant | — |
| **32** | ඉඩමක් හුවමාරු කිරීමේ සාධන පත්‍රය | **Exchange of Land** | s.43 |
| **24** | ඇපයක් වෙනුවෙන් පවරන ලද සාධන පත්‍රය | **Transfer given as Security/Surety** (+ its release) | s.43 |
| **27** | න්‍යාසය අවලංගු කිරීමේ සාධන පත්‍රය | **Cancellation of a Trust** | s.43 |

### B. Additional transaction forms per `manifest.json` (pages 1–27, not in the read range — labels below are the manifest's own; treat with caution given the errors found)

Form 08 Instrument of Transfer/Sale; Form 09 Instrument of Mortgage; Form 10 Instrument of Lease; Form 11 Instrument of Caveat; Form 12 Withdrawal of Caveat; Form 13 Power of Attorney; Form 29 Cancellation of Lease; Form 31 Registration of Address; Form 30 Revocation of Power of Attorney; Form 23 Agreement to Sell; Form 07 Application for Amalgamation/Subdivision.

> These earlier forms' images (pages 1–27) were **not** in the read range, so
> they were not OCR'd; the titles are taken from the manifest and are
> unverified.

### C. Manifest label errors detected (manifest vs. what the page actually prints)

- **Form 25** — manifest says "Registration of Judgment"; **printed = Certificate of Sale**.
- **Form 26** — manifest says "Cancellation of Judgment Registration"; **printed = Cancellation of Agreement to Sell**.
- **Form 24** — manifest says "Instrument of Gift"; **printed = Transfer given as security**.
- **Form 27** — manifest says "Discharge of Mortgage"; **printed = Cancellation of Trust**.
- **Form 32** — manifest says "Application for Partition"; **printed = Exchange of Land**.
- **Form 19 / 19A** — manifest labels both "Title Certificate"; **printed = Title *Register*** (the certificate is Form **14/14A**, which the manifest omits entirely).

---

## 3. Per-transaction: documents required + process steps

The RTA transactional forms share one skeleton (detailed in §4). Below are the
transaction-specific requirements as printed.

### Cancellation of Agreement to Sell — Form 26 (s.43)

- Documents/data: land identification block; prior registration reference
  (title-certificate no. + title class); the agreement's period and effective
  date; seller and buyer identities (name/NIC/address); gross & net
  consideration; reason and date of cancellation; registration fee +
  stamp-duty receipts.
- Process: instrument executed by buyer and grantor → witnessed → notary
  attests under s.44 → lodged at the title-registry office (office-use box
  records date/time/receipt/receiving officer) → **registered in the title
  register (හිමිකම් ලේඛනය) at the stated folio by the Registrar of Title**.

### Conversion to Condominium — Form 21 (s.50)

- Documents/data: applicant identity; land details; nature of the condominium
  property (temporary / permanent / common); **condominium plan particulars**
  (surveyor name, plan number & date, cadastral map number); a declaration
  invoking the **Apartment Ownership Law No. 11 of 1973 (as amended, 2003)**;
  fee.
- Process: applicant completes and signs → lodged with the Registrar of Title
  → registered so the building's horizontal subdivision is recorded. (Fee
  schedule item 7 links this to application under s.50(1) = Rs.100;
  registration of the horizontal subdivision = Rs.1000.)

### Registration of a Certificate of Sale — Form 25 (s.43)

- Documents/data: land details; prior registration; original decree/undertaking;
  value of the certificate of sale; **authorized auctioneer** particulars;
  **creditor/mortgagee** particulars; **purchaser** particulars; fees.
- Process: completed and signed by the **auctioneer and the
  creditor/original institution** → witnessed → notary attestation (s.44) →
  lodged → registered in the title register by the Registrar of Title. (This
  is the post-auction / fiscal-sale title transfer.)

### Certificate of Title — Form 14 & 14A (s.37; notes s.65)

- This is an **output document the Registrar issues**, not a party-executed
  instrument. Contents: identification header (folio, province, district, DS,
  GN, name, address, cadastral map no., block/parcel no., land use, extent,
  land nature); **First Schedule = proprietorship**; **Second Schedule = plan
  of land**; **Third Schedule = encumbrances ledger** (prior registrations,
  notaries, registered/cancelled dates). Bears national emblem + two lion
  motifs; signed by the **Registrar of Title**.
- Process (per fee schedule): applied for under **s.37(1)** (Rs.500); a copy
  obtainable under **s.15(4)** (Rs.500).

### Title Register — Form 19 (private) & 19A (State land)

- The **register folio itself** (the master record). Contents: land part; First
  Schedule (ownership — private owner details, or for 19A the State
  controlling officer/agency/ministry); Second Schedule (charges); Third
  Schedule; "other details" (dues to State/local authority,
  improvements/natural resources, other remarks, cross-notes). Signed by the
  Registrar of Title (Form 19) / Registrar of Lands (Form 19A).
- Process: this is the authoritative register maintained by the registry; all
  instruments above are entered against it. Inspection under s.34(1) (Rs.100);
  certified extract under s.34(2) (Rs.250).

### Exchange of Land — Form 32 (s.43)

- Documents/data: **parallel land details for both parcels** ("first land
  part" / "second land part", each with its own office-use box); prior
  registration; first-party and second-party identities; consideration (value
  of each parcel); fees; conditions.
- Process: executed and signed by **both parties** → witnessed → notary
  attestation (s.44) → lodged (two office boxes, one per parcel) → each
  parcel's title register updated by the Registrar of Title.

### Transfer Given as Security — Form 24 (s.43)

- Documents/data: land details; prior registration; **pledgor/transferor
  (ඇපකරු)**; **security-taking institution** (name, registration no.,
  registered address — bank/business); duration the security is valid;
  property value; fees; conditions; encumbrances table. Item 11 provides for
  the **release/cancellation of the security bond** by the security-taker.
- Process: pledgor and security-taker sign → witnessed → notary attests
  (s.44) → lodged → registered against the title. On satisfaction, the
  release (item 11) is executed by the security-taker and registered.

### Cancellation of Trust — Form 27 (s.43)

- Documents/data: land details incl. extent of land under the trust; prior
  registration; **settlor/trustor (න්‍යාසාදායක)**; the party to whom
  cancellation is granted; conditions in the trust instrument; **details of
  the trust deed being cancelled** (number, notary, date); fees; grounds for
  cancellation; encumbrances. Declaration and signatures involve the settlor
  and any **life-interest holder**.
- Process: settlor (and life-interest holder, if any) sign → witnessed →
  notary attestation (s.44) → lodged → cancellation registered against the
  title.

### Relinquishment/Cancellation of Life Interest — (form tail on p28; manifest = Form 28, s.44)

- Documents/data (from the visible tail): reason for cancellation; fees;
  declaration to register cancellation of the life interest; signatures of
  the **life-interest holder** and the **owner**; witnesses; notary
  attestation.
- Process: executed by life-interest holder + owner → witnessed → notary
  attests → registered in the title register.

---

## 4. Cross-cutting notes (shared structure, prerequisites, printed caveats)

- **Shared instrument skeleton** across all transactional forms (21, 24, 25, 26, 27, 32, and the life-interest form):
  1. **Office-use box** (කාර්යාලීය ප්‍රයෝජනය සඳහා පමණි): date, time, entry number, fees — **stamp duty (මුද්‍දර ගාස්තු)** and **registration fee (ලියාපදිංචි කිරීමේ ගාස්තු)** each with a receipt number (ලුදුපත් අංකය) — title-certificate number, and receiving officer (භාරගත් නිලධාරියා). The right half records **"registered in the title register (හිමිකම් ලේඛනයේ ලියාපදිංචි කරන ලදී) at folio ___"** with the **Registrar of Title's** signature and date.
  2. **Land identification block**: district, DS division, GN division, street/village/town, valuation number, cadastral map number, block/parcel number, extent, and (where relevant) condominium unit number.
  3. **Prior registration** (පූර්ව ලියාපදිංචිය): place registered, title-certificate number, title class.
  4. **Parties**, **consideration/value**, **fees**, **conditions**.
  5. **Declaration + party signatures + dates**.
  6. **Witnesses table**: full name / NIC (ජාතික හැඳුනුම්පත් අංකය) / address / signature.
  7. **Notary attestation (සහතික කිරීම)** by a **Notary Public (ප්‍රසිද්ධ නොතාරිස්)** with **signature and official seal (අත්සන සහ නිල මුද්‍රාව)**.
- **Recurring statutory footnote (caveat printed on the instruments):** parties and witnesses must sign **in the presence of the notary**, and the notary must attest **after conducting the examination of particulars required under s.44 of the RTA No. 21 of 1998**. (Appears verbatim on pages 28, 30, 34, 44, 46, 48.)
- **Section pattern:** transactional/dealing instruments are lodged under **s.43**; the owner's **Certificate of Title** is issued under **s.37** (with s.65 notes); **condominium** conversion under **s.50**; **notary examination/attestation** under **s.44**; inspection/extracts/caveat/certificate applications under **ss.34, 36, 37, 15** (fee schedule).
- **Registrar roles:** private-land title matters are signed by the **Registrar of Title (හිමිකම් පිළිබඳ රෙජිස්ට්‍රාර්)**; the State-land register (Form 19A) is signed by the **Registrar of Lands (ඉඩම් රෙජිස්ට්‍රාර්)**.
- **Condominium cross-reference:** Form 21 is grounded in the **Apartment Ownership Law No. 11 of 1973 (as amended 2003)**, i.e., a distinct regime bridged into the RTA register.
- **Interface-spec linkage:** `docs/reference/draftly-interface-spec.md` treats RTA as the only active v0 regime and states that *"the shared deed schedule and prescribed RTA forms take priority over a general document generator"* (line 328), with the workflow library seeded by *"RTA examination, drafting, execution, and attestation workflows"* (line 346). It does **not** enumerate individual forms — these gazette pages are the actual form corpus behind that.

---

## 5. The fee schedule (Second Schedule, page-48) — transcribed

### Application fees (ඉල්ලුම්පත්‍ර ගාස්තු)

Column: section (වගන්තිය) / purpose / fee (Rs.):

1. **s.34(1)** — application to inspect the Title Register — **100**
2. **s.34(1)** — application to inspect the cadastral map (කැඩැස්තර සිතියම) — **100**
3. **s.34(2)** — obtaining an extract from the Title Register — **250**
4. **s.34(3)** — obtaining a copy of the cadastral map — **500**
5. **s.36(1)** — application to enter a caveat / note (අනතුරු ඇඟවීමක්) in the register — **100**
6. **s.37(1)** — application to have a Certificate of Title issued — **500**
7. **s.50(1)** — application to register a horizontal subdivision (condominium) in a building — **100**
8. **s.15(4)** — obtaining issue/copy of a Certificate of Title — **500**

### Registration fees (ලියාපදිංචි කිරීමේ ගාස්තු)

Purpose / fee (Rs.):

1. Mortgage instrument (උකස් සාධන පත්‍රය) — **200**
2. Address (ලිපිනය) — **25**
3. Lease instrument (බදු සාධනපත්‍රය) — **200**
4. Caveat order (කේවියට් ආඥාව), per each six months — **200**
5. Cancellation instrument (අවලංගු කිරීමේ සාධන පත්‍රය) — **200**
6. Transfer instrument (පැවරීමේ සාධන පත්‍රය) — **500**
7. Trust instrument (න්‍යාස සාධන පත්‍රය) — **500**
8. Registering a horizontal subdivision in a building (condominium) — **1000**
9. Registering an amalgamation or subdivision (ඒකාබෙදීම/අතුරු බෙදීම) — **1000**
10. Agreement-to-Sell instrument (විකිණුම් ගිවිසුම් සාධන පත්‍රය) — **500**
11. Certificate-of-Sale instrument (විකුණුම් සහතික සාධන පත්‍රය) — **500**
12. Other instruments prescribed under the Title Act — **500**
13. Other instruments registrable in the Title Register — **500**

---

## 6. Ambiguities / partially illegible items

- **Form 27 (Cancellation of Trust, pages 46–47)** — the item-4 label and the
  closing declaration mix **trust**, **gift (තෑගිකර)**, and **life-interest
  (ජීවිත භුක්තිය)** wording. This may be a drafting artifact of the gazette,
  or OCR of small print; the exact legal relationship between "trust
  cancellation" and the "life-interest holder" signatory should be verified
  against the clean PDF before relying on it. (Legal wording is human-owned
  per repo rules — flagging, not resolving.)
- **Amended-Act year on Form 21 (page-32)** — the declaration cites the
  Apartment Ownership Law "as amended by Act No. … of 2003"; the amendment
  **number** is not clearly legible in the scan.
- **Form 24 title nuance (page-44)** — *"ඇපයක් වෙනුවෙන් පවරන ලද සාධන පත්‍රය"*
  rendered here as "transfer given as security/surety"; whether this is a
  security-transfer, a conditional transfer, or a guarantee bond is a
  legal-classification question worth confirming.
- **Blank template tables (pages 36, 38–41)** — these are empty
  register/schedule grids (no data), so column meanings are inferred from
  headers; a couple of narrow rotated headers on page-36 were low-resolution.
- **Manifest ↔ image page mapping** — `manifest.json`'s `pdfPages` are
  indices into `1886-58_S.pdf`, which are offset from the `page-NN.png`
  gazette page numbers; do not assume `pdfPages:[44,45]` equals
  `page-44/45.png`. Use the printed *"ආකෘති පත්‍ර අංක"* to identify a form,
  not the manifest mapping.
- **Pages 1–27 not examined** — outside the read range (pages 28–48), so
  Forms 07–13, 23, 28, 29, 30, 31 are reported from the manifest only and are
  unverified against their images.
