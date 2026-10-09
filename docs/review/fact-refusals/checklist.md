# Fact refusal guidance review

## Behavior

Fact-review errors now distinguish an expired sign-in session, a practising-status
refusal, missing role permissions and an unclassified access refusal. Session
errors link to sign-in. Practising-status errors link to the existing notary
profile and explain when administrator help is needed. Role errors explain that
the administrator must check access; they do not link to an unrelated profile field.

Quick acceptance keeps its warning when detailed review opens. Once the review
panel displays the same refusal for that fact, only the panel's alert is shown.
Closing or renewing the panel restores the quick warning as needed. Stale-version
responses retain review guidance. Requests, version checks, retry keys and backend
authorization are unchanged.

## Independent review

Two findings were verified and resolved:

- Opening detailed review previously hid the warning before a replacement existed.
  Suppression now requires the same fact, status and error code in the panel.
- The capability error offered a profile link, but profiles cannot change roles.
  That link was removed from capability errors.

Independent re-review found no important remaining issues. No authorization bypass
or optimistic fact confirmation was introduced.

## Verification

| Check | Result |
| --- | --- |
| Typecheck, full frontend lint, production build | PASS |
| Targeted refusal and fact-register tests | PASS: 45 tests, including the additional StrictMode regression |
| Full test suite and coverage | PASS: 894 tests in 95 files; branches 84.15%, functions 79.37%, lines/statements 72.06% |
| Approved global branch floor | Unchanged at 75%; all configured coverage thresholds passed |
| Synthetic browser acceptance | PASS: warning remains on opening review; two refused POSTs leave one alert and no confirmation |
| Browser accessibility and runtime | PASS: zero axe violations and zero page errors |
| English/Sinhala error mapping | PASS: localized tests cover the new guidance |

The first concurrent full test run hit the existing tooltip test's 30ms timing
assumption. A complete rerun with two workers passed, with no tooltip or threshold
changes. The additional StrictMode regression also passed separately.

Browser fixtures contain synthetic facts, a synthetic actor and mocked refusal
responses. The initial browser fixture lacked the history contract's `decisions`
array; correcting that fixture resolved its render failure. The final screenshot
and `fact-refusal-browser-results.json` record the passing journey.

## Account limitation

This fixes the misleading and duplicate error display. The actual account's
backend refusal code and practising status have not been verified. Missing or
expired practising approval can still legitimately block acceptance. This change
does not grant roles, create certificate approvals or weaken that policy.
