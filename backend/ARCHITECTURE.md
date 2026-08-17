# Backend architecture map

Orientation doc. Read this before reading code — it exists so you never have to
hold the whole backend in your head at once.

For *why* a rule exists, see `backend-implementation-plan-v0.md` (structure and
invariants) and `docs/api-conventions.md` (HTTP rules). For the legal
requirements the code implements, see `../docs/draftly-rta-matter-workflow-v1.md`
— code comments cite it by section, like `(§9.3)`.

## The 30-second version

`src/modules/` has **24 directories, but only 10 contain code.** Start by
ignoring the other 13 — they are empty placeholders for services that are
planned but not built:

```text
billing  corpus_governance  export  library  memory  notarial_register
notification  obligations  party  research  retention  storage  voice
```

The ten real ones are `auth`, `audit`, `content_governance`, `matter`, `task`,
`document`, `verification`, `check`, `draft`, `approval`. Every one has the
**same seven parts**, so learn the shape once and all ten read the same way.

Nothing is clever. The code is large because Sri Lankan land law is large.

## Module anatomy

Every module is this, and you can usually ignore four of the seven while
learning:

| Part | What it does | Read it? |
| --- | --- | --- |
| `api/router.py` | HTTP only: authorize, parse, serialize | Yes |
| `api/schemas.py` | Request/response wire shapes | Skim |
| `application/*.py` | Orchestrates one operation | On writes |
| `domain/*.py` | **The actual rules.** Pure Python | Yes — this is the point |
| `ports.py` | "I need something shaped like this" (Protocols) | No — declarations only |
| `contracts.py` | The only thing *other* modules may import | Yes — it's tiny |
| `infrastructure/` | Postgres, filesystem, Gemini | When debugging data |

`domain/` never imports FastAPI, SQLAlchemy, or a provider SDK. That is what
makes the rules testable without a database — and why most tests run in
milliseconds.

### The one rule that makes it navigable

> A module may never import another module's `domain`, `orm`, `repository`, or
> `infrastructure`. Only its `contracts.py`.

So when you wonder "how does approval talk to drafting?", the answer is always
in a `contracts.py` — and those are 26–57 lines each. Reading all four gives you
the entire cross-module map in ten minutes:

- `check/contracts.py` — issue gates, for draft and approval
- `task/contracts.py` — checklist blockers, document links
- `verification/contracts.py` — the confirmed-fact tier
- `draft/contracts.py` — form snapshots, for approval

## Module map

Ordered roughly by how a matter flows through them.

| Module | Owns | Tables |
| --- | --- | --- |
| `auth` | Users and their external identities | `users`, `user_identities` |
| `audit` | Append-only audit events | `audit_events` |
| `content_governance` | **The rule pack**: taxonomy, questions, checklist definitions, check definitions, form templates, sources. Platform-wide, not per-tenant | none (code-defined) |
| `matter` | What transaction this is, who may reach it, how much Draftly may automate | `matters`, `matter_classifications`, `matter_intake_answers` |
| `task` | The compiled checklist a matter is worked under, item state, document links | `checklist_snapshots`, `checklist_items`, `checklist_satisfaction_links` |
| `document` | Uploaded evidence, detected documents, fragments, processing runs | `source_files`, `detected_documents`, `document_fragments`, `source_file_processing_runs` |
| `verification` | Extracted facts, their versions, evidence, review decisions | `evidence_references`, `extracted_facts`, `review_decisions` |
| `check` | Deterministic cross-document checks and the legal issues they raise | `cross_document_checks`, `legal_issues` |
| `draft` | Generated forms and their evidence-linked field bindings | `generated_forms`, `generated_form_fields` |
| `approval` | Lawyer approval, export, registration events | `approvals`, `form_exports`, `registration_events` |

`content_governance` is the odd one out: it has no tables. The rule pack is
defined in code under `domain/rta/` and pinned by version wherever it is used,
so a matter always records which rule version produced its checklist.

## Following one request

`GET /api/v1/matters/{id}/issues` — three hops, and only two of them think.

1. **`check/api/router.py`** — `_authorize(...)` then serialize. The one real
   decision: gates are computed over **every** issue on the matter, never the
   filtered page, so filtering to `WARNING` cannot make a blocked matter look
   clear.
2. **`check/application/check_service.py`** — for this read, a pure
   pass-through. See "Honest notes" below.
3. **`check/infrastructure/repository.py`** — the SQL. Note `user_id` is the
   first predicate; that is the tenancy boundary, and it is first in *every*
   query in the codebase.

Writes are where `application/` earns its keep: `run_checks` reads confirmed
facts, executes the runners, creates issues, and appends an audit event — all in
one transaction.

## I want to change X

| Goal | Go to |
| --- | --- |
| Add or change a checklist requirement | `content_governance/domain/rta/checklist.py` |
| Add a deterministic check | `content_governance/domain/rta/checks.py` (definition) + `check/domain/runners.py` (logic) |
| Change what routes a matter out of automation | `content_governance/domain/rta/eligibility.py` |
| Change who may do what | `content_governance/domain/rta/workflow_roles.py` |
| Add a form template | `content_governance/domain/rta/forms.py` |
| Change intake questions | `content_governance/domain/rta/questions.py` |
| Change how a form field gets its value | `draft/domain/policies.py` |
| Change approval preconditions | `approval/domain/policies.py` |
| Change the approval declaration | `approval/domain/declarations.py` — **legal wording is human-owned; escalate** |
| Add an endpoint | the module's `api/router.py`, then check `docs/api-conventions.md` |
| Wire a new service or adapter | `src/bootstrap.py` — the only file allowed to see both a port and its implementation |
| Add a table | the module's `infrastructure/orm.py` + a migration + register in `migrations/env.py` |

## Invariants that explain otherwise-odd code

When code looks paranoid, it is usually one of these:

1. **Every row carries `user_id`, and every query filters on it first.** That is
   the tenancy boundary in this deployment.
2. **Every material mutation appends an audit event in the same transaction.**
   Not after, not best-effort.
3. **Original evidence is immutable.** Source files are write-once; nothing has
   a delete path. Superseding points forward instead.
4. **Machine output is never authoritative.** A model proposes; only a human
   confirms. A correction creates a **new fact version** rather than editing one.
5. **A form binds a specific fact version**, not "whatever is current" — which
   is why correcting a fact can mark an approved form stale rather than silently
   changing it.
6. **Status is never colour alone**, and an unresolved field renders a named
   token like `[[UNRESOLVED: transferee_nic]]` — never blank space, never an
   invented value.
7. **Statutory blockers cannot be waived by anybody**, at any role, with any
   rationale. Overridable blockers can; statutory ones cannot.

## Where the law actually lives

`content_governance/domain/rta/` is the largest and most important directory —
about 10k lines. It is data-heavy rather than logic-heavy, so read it *after*
you have seen a module consume it.

| File | Lines | What |
| --- | --- | --- |
| `checklist.py` | ~2.5k | Requirement definitions and checklist modules |
| `forms.py` | ~1.1k | Prescribed form templates and their fields |
| `taxonomy.py` | ~1.1k | Instruments, families, subtypes |
| `documents.py` | ~740 | Document classes |
| `checks.py` | ~660 | Check definitions |
| `eligibility.py` | — | What Draftly may automate, and the statutory stop conditions |
| `workflow_roles.py` | — | Capability map; approval is responsible-lawyer only |

## Tests are the documentation

Test names are deliberately English sentences stating legal rules. Skimming the
function names of a test file teaches the rules faster than reading the
implementation:

```text
test_part_parcel_disposition_creates_the_section_47_statutory_blocker
test_a_settlement_letter_does_not_clear_an_uncancelled_mortgage
test_unknown_ownership_is_an_unmet_predicate_but_not_a_mismatch
test_only_the_responsible_lawyer_may_approve_a_form
test_export_can_never_imply_registration
```

Start with `content_governance/tests/test_eligibility.py` and
`approval/tests/` — between them they state most of the safety-critical
behaviour.

## Running things

All commands from `backend/`, using `uv` only — never pip or Poetry.

```bash
uv run pytest                    # full suite
uv run pytest src/modules/check  # one module
uv run mypy src                  # strict
uv run ruff check .
uv run ruff format .
uv lock --check
uv run alembic heads             # must be a single head
uv run alembic current           # what the database actually has
uv run alembic upgrade head      # apply pending migrations
```

### Running the server on Windows: `--reload` is not optional

```bash
uv run uvicorn src.main:app --reload --port 8000
```

**Drop `--reload` on Windows and every database query fails** with
`/health/ready` returning `{"status": "degraded", "db": "unreachable"}`.

uvicorn ≥ 0.52 builds its event loop from a factory and picks
`ProactorEventLoop` on Windows unless it is running a subprocess. psycopg's
async mode refuses to run on that loop. `--reload` and `--workers` set
`use_subprocess`, which selects `SelectorEventLoop` and makes it work.
`--loop asyncio` does **not** help, and neither does the
`set_event_loop_policy` call in `src/main.py` — uvicorn no longer consults the
policy. Deployed Linux hosts are unaffected.

### The two database URLs are not interchangeable

| Variable | Used by | Endpoint | Scheme |
| --- | --- | --- | --- |
| `DATABASE_URL` | the app (async) | pooled, `-pooler` in host | `postgresql+psycopg://` |
| `DATABASE_URL_DIRECT` | Alembic (sync) | direct, no `-pooler` | either; `env.py` rewrites it |

A bare `postgresql://` scheme resolves to psycopg2, which is synchronous —
Alembic is happy, the app dies with `The asyncio extension requires an async
driver`. Neon's console hands you the bare form, so this is easy to get wrong.

## Honest notes

Things worth knowing that the code will not tell you.

- **Some indirection does not pay for itself.** On read paths, `application/`
  methods are often one-line pass-throughs to the repository. They exist for
  uniformity, not behaviour. Skim past them; they are not hiding anything.
- **Two ports are wired to adapters that live in the owning module**, because
  approval writes into aggregates it does not own:
  `draft/infrastructure/form_commands.py` and
  `matter/infrastructure/workflow_commands.py`. They are connected in
  `bootstrap.py`, which is the only place permitted to see both sides.
- **An illegal matter-state transition is logged and refused, not raised** (see
  `matter/infrastructure/workflow_commands.py`). The approval or registration
  event is the legally meaningful record and is already written; raising would
  roll back a lawyer's recorded act because a derived field could not follow.
  This is a deliberate choice and a reasonable one to revisit.
- **No candidate-fact reader is wired** into `draft`, so non-critical form
  fields stay unresolved rather than being prefilled from raw extraction.
  Intentional: the alternative is showing a value nobody verified.
- **None of the 32 form templates is `registration_ready_capable`.**
  Registration-ready export is impossible by construction until a lawyer
  verifies templates. Verify with
  `forms.require_template(i).registration_ready_capable`.
- **`document/__init__.py` has a placeholder docstring** while every other
  module describes what it owns. Cosmetic, but it is the one gap in the
  module-level documentation.
