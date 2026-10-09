# Extraction coverage status

Owner approved the four-class, 51-observation synthetic basis and targets: at least 95% precision, 90% readable-supported-field recall, and 100% correct source-page attribution. The full benchmark was not executed after the explicit test/benchmark waiver. These targets remain unverified.

| Supported class | Approved registry observation fields |
| --- | --- |
| identity-card | transfereeNic, holderNameEn, holderNameSi, holderDateOfBirth, holderAddress |
| title-certificate | titleCertificateNo, cadastralMapNo, blockNo, sheetNo, parcelNo, extent, district, dsDivision, gnDivision, classOfTitle, ownerName, placeOfRegistration |
| survey-plan | surveyPlanNo, surveyorName, surveyorRegistration, landName, lotNo, extent, boundaryNorth, boundaryEast, boundarySouth, boundaryWest |
| form8-instrument | district, dsDivision, gnDivision, village, assessmentNumber, cadastralMapNo, blockNo, sheetNo, parcelNo, extent, extentSubjectToTransfer, placeOfRegistration, titleCertificateNo, classOfTitle, transferorName, transferorNic, transferorAddress, transfereeName, transfereeNic, transfereeAddress, consideration, considerationWords, notaryName, notaryCode |

The identity-card provider field transfereeNic is a legacy observation name for the printed holder NIC. Current canonical extraction records holder identity and requires a lawyer association before assigning a transfer role; the reference value is unchanged.

A pre-waiver clean-card provider diagnostic returned 46 correctly mapped observations with page-one attribution. It does not establish robustness, valid Sinhala rendering, persistence or improvement against the approved complete reference. Five observations were previously filtered by mapping: holderNameEn, holderNameSi, holderDateOfBirth, holderAddress and surveyorRegistration. Their mapping is now supported in code; extraction after this mapping change remains unmeasured.

Multiple-subject, conflict, missing, unsupported, rotated/scanned and failure variants are in the approved basis. Full outcomes for those variants remain unmeasured under the waiver. The initial Sinhala image-rendering issue prevents a Sinhala accuracy claim from the early diagnostic.

Classes and fields outside the registry remain unsupported by this automatic extraction path; manual evidence review/input is required. Classification vocabulary and schema inspection alone are not extraction accuracy. The attestation-date workflow consumes eligible lawyer-reviewed canonical facts and does not infer a date from unreviewed observations.

The permitted real-case API run persisted 113 unreviewed candidates across seven files and 26 pages. Supporting text/page locators were available, with 106 text-level and seven page-level attributions; semantic correctness, grouping, subject associations and verified legal facts were not measured. Candidate counts and literal matching are not accuracy.
