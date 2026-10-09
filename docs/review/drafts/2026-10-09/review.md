# Drafts transaction setup review

Focused regression review against base `5f81aa6`. All matter, actor and
association data in these captures is synthetic.

## Behavior and evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Empty transactions | PASS: explanation and primary setup action; no selectors | `empty-1440.png`, `empty-1024.png` |
| Setup navigation | PASS: Facts hash opens Subjects and transactions, focuses summary; Add party enabled | `setup-1440.png` |
| Saved associations | PASS: explicit transaction enables New draft; parcel and party roles selected individually | `selected-1440.png`, `selected-1024.png` |
| Generation request | PASS: Form 8 request pins association version and all explicit subject IDs | Payload below |
| Accessibility | PASS: scoped axe found zero serious/critical violations in empty scope, selected scope and transaction setup | Browser run |
| Mobile overflow | PASS: document width and scroll width both 390px in empty and selected states | Browser run |
| Visual review | PASS: stable desktop captures show readable hierarchy, visible setup action and unclipped controls | Attached captures |

The real Drafts page sent this request and navigated to
`/matters/mat-1/drafts/synthetic-form`:

```json
{
  "templateId": "reg_2022_form_08",
  "scope": {
    "transactionId": "tx-1",
    "associationVersion": 3,
    "parcelSubjectId": "parcel-1",
    "transferorSubjectId": "party-1",
    "transfereeSubjectId": "party-2"
  }
}
```

## Mechanical gates

Commands ran on the final implementation over `5f81aa6`, using the original
authentication hook. Each exited 0:

- `pnpm exec vitest run src/components/editor/form-scope-selector.test.tsx src/components/matter/facts-screen.test.tsx --maxWorkers=2 --minWorkers=1`:
  2 files, 41 tests passed. Covers loading/error/empty distinctions, missing
  associations, explicit selections, pagination refusal and both hash entries.
- `pnpm lint`: zero warnings.
- `pnpm build`: production compilation, type validation and 18 static pages
  completed, using synthetic build-time Clerk configuration.
- `pnpm typecheck`: passed after the build.

Full coverage remains a PR CI gate. This review does not change its thresholds.

## Review boundary and repairs

The browser used intercepted synthetic API responses and a temporary token
stub in the isolated worktree. That stub was restored exactly before staging;
production authentication code has no diff. Browser navigation ran on port
4312 to avoid another local server. Desktop captures use 1440×900 and 1024×768;
the additional overflow check uses 390×844.

The browser verifies scope entry, hash focus, explicit selection, generation
request and editor URL. It does not verify subject creation persistence,
backend authentication, rendered editor, legal approval or export. The editor
GET intentionally returned a synthetic 503 at this boundary; its expected
resource errors and canceled Next route prefetches are recorded in the local
raw browser log. No browser page exceptions occurred.

Harness repairs: use an explicit browser context for axe, allow synthetic
authorization preflights, query nested select labels by accessible name prefix,
and wait for responsive layout transitions before captures. Re-running passed.

Missing roles stay unresolved; no role assignment or legal readiness is inferred.
Prescribed form text and approval rules are unchanged. Sinhala guidance is
covered by component regression assertions; full Sinhala zoom review was not
part of this focused browser run.
