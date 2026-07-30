# obligations_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md` and
`matter-service.md`. One markdown per service under `backend/docs/services/`.

This is a **thin** service. It backs the home dashboard's deadline list —
notary licence renewals, mandatory lawyer-review deadlines, and other
date-driven obligations — and nothing more. It is documented separately because
it is a distinct read the dashboard makes, but it may fold into
`matter_service` (§7).

## 1. What it owns

A read of **date-driven obligations** shown on the home dashboard: each a
label, a due date, and a status. It answers "what is coming due" so the
dashboard can surface renewals and review deadlines before they lapse.

It does **not** compute legal deadlines, run checks, verify anything, or feed a
draft. It stores and serves obligation records and their status against a due
date. Where the obligations come from — who creates them and how their status
advances — is the unresolved part (§6).

## 2. Where it sits

```text
GET /obligations ─→ api/v1/obligations.py ─→ application/obligations_service.py
                                                        │
                                                        │ orchestrates
                                                        ▼
                                          domain/obligations.py
                                          ports: ObligationRepository, AuditPort
```

The router authenticates and parses only. The service takes an authenticated
`RequestContext` and returns the actor's obligations. Infrastructure implements
the ports. The service imports no SQLAlchemy and no FastAPI.

Frontend path today is mocked at `GET /api/obligations` (`src/lib/data.ts`
`getObligations`), which returns a flat list from `src/lib/mocks`. Under
`/api/v1` this is `GET /obligations`. There is no obligations row in the plan's
§7 API surface yet — this service adds one.

## 3. Domain model it needs

In `domain/obligations.py`, mirroring the frontend `Obligation` type
(`frontend/src/types/obligation.ts`) field-for-field:

- **Obligation** — `id`, `matterId`, `labelKey`, `dueDate` (string, ISO date),
  `status` (`ObligationStatus`).

`labelKey` is a key, not free prose — the frontend renders it through its
i18n/label layer. Five fields, one enum. That is the whole model.

`ObligationStatus` lives in `domain/enums.py`, values exactly as the frontend
declares them:

| Enum | Values |
| --- | --- |
| `ObligationStatus` | `upcoming`, `due`, `overdue`, `complete` |

Status tracks `dueDate`: an obligation moves `upcoming → due → overdue` as its
date approaches and passes, and to `complete` when the underlying task is done.
Whether the service derives that transition from the date or stores it as set is
an open decision (§6).

## 4. Domain tie-in

The obligations are not decorative. The mentor's deterministic rules include a
notary's **annual licence renewal** and a **mandatory lawyer review** — both
are real, dated duties a notary must not miss. An obligation record encodes one
such deadline so the dashboard warns before it lapses. The service stays thin,
but the deadlines it carries are load-bearing legal duties, which is why status
accuracy matters more than the field count suggests.

## 5. The method

### list_obligations(ctx) -> list[ObligationRead]

Returns the obligations relevant to the actor. The mock returns a single flat
list with no filtering; in production this must scope to what the actor may see
— which, given the `matterId` field, means the matters the actor is a member of
(resolved the same way `matter_service` resolves membership, §4 there). A
licence-renewal obligation that is per-notary rather than per-matter does not
fit that scoping cleanly (§6). Reads only; no mutation method is defined here
until obligation authorship is settled (§6).

## 6. The gaps to record

Two unresolved things, both about where obligations come from and what they are
scoped to:

- **Every obligation carries a `matterId`, but a licence renewal is
  per-notary.** A notary's annual licence renewal is not tied to any one
  matter — it is a duty of the person. The `matterId` field forces every
  obligation to be matter-scoped, so a per-notary duty has no clean home. Either
  `matterId` becomes optional (a per-notary obligation with no matter), or
  per-notary duties live somewhere else and only matter-scoped deadlines
  (lawyer-review) use this service.
- **Who computes and advances status is unspecified.** Nothing here derives a
  due date or flips `upcoming → due → overdue`. That could be a scheduled job
  over `dueDate`, a write from the service that owns the underlying duty (the
  check or task service for a review deadline), or a manual set. The frontend
  only reads; the write path is undefined.

## 7. Should this even be its own service?

Probably not, on its own merits. It is five fields, one enum, one read, and it
is matter-scoped through `matterId` — everything `matter_service` already does.
Folding `list_obligations` into `matter_service` would remove a service with
almost no behaviour. It is kept separate in this doc for one honest reason: the
home dashboard reads obligations as a **cross-matter list** (all the actor's
deadlines at once), which is a different shape from `matter_service`'s
single-matter reads, and the per-notary licence-renewal case (§6) may not be
matter-scoped at all. If those two pull obligations away from the matter
aggregate, a thin standalone service earns its place; if not, fold it in. This
is the first open decision (§8).

## 8. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Fold into `matter_service` or keep standalone** — decide once the
   per-notary case (§6) is settled. Lean **keep the read standalone for the
   cross-matter dashboard, back it with the same store, and revisit if it stays
   trivial.**
2. **`matterId` optional for per-notary obligations** — to fit licence renewal,
   which is not matter-scoped. Lean **make `matterId` nullable and scope
   per-notary obligations to the actor**, but this changes the frontend type,
   so it needs frontend sign-off before the contract freezes.
3. **Status derivation and the write path** — job-driven from `dueDate`, written
   by the owning duty's service, or manual. Lean **a scheduled sweep advances
   `upcoming → due → overdue` from `dueDate`; `complete` is set by whoever
   completes the underlying task.**
4. **Audit scope** — whether obligation status changes are material mutations
   under §5.3.8. Lean **audit `complete` and any manual override; skip audit
   for pure date-driven `upcoming → due → overdue` ticks.**
