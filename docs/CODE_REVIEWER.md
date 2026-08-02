# Draftly pull-request review pipeline

This document defines the AI-assisted review pipeline for this repository.
AI review is advisory: deterministic CI and a human reviewer remain the merge
authority.

## Model policy

### Normal pull requests

- Model: `gpt-5.4-mini`
- Reasoning effort: `medium`
- Trigger: pull request opened, reopened, marked ready, or review requested

GPT-5.4 mini is the default because it is optimized for coding and high-volume
workloads while keeping review cost low. For eligible OpenAI organizations that
opt into API input/output sharing, it is currently part of the larger
complimentary-token model group. Eligibility must be confirmed in the OpenAI
Platform data-control settings; it is not automatic.

### Sensitive but routine pull requests

- Model: `gpt-5.4-mini`
- Reasoning effort: `high`
- Trigger: a trusted repository collaborator requests it manually

Use this level when a pull request makes a meaningful change within an
established sensitive area, including:

- Authentication, session, authorization, or organization-isolation logic
- Matter permissions, roles, or audit-log behavior
- Billing, subscription, or payment behavior
- Document storage, upload, export, deletion, or privacy controls
- Lawyer approval gates or verified-fact enforcement
- Legal-corpus ingestion, retrieval boundaries, or citation grounding
- Additive or reversible database migrations
- Secret handling, CI permissions, or deployment configuration

Do not escalate merely because a PR touches one of those folders. Documentation,
tests, type-only changes, copy changes, mechanical refactors, generated files,
and changes that do not alter the sensitive behavior remain normal reviews.

Run a sensitive review with:

```text
/review --config.reasoning_effort="high"
```

Critical changes use the same model at high reasoning effort. This includes new
trust boundaries, cross-organization access risks, approval or audit bypasses,
destructive migrations, production credential changes, and confirmed security
or privacy vulnerabilities. The team does not use a different model tier for
these reviews.

Only comments from repository owners, organization members, or collaborators
can start the workflow.

### No quota-based model fallback

Do not configure a deprecated or weaker model as an automatic fallback after
the complimentary allowance is exhausted. OpenAI bills a request that exceeds
the allowance instead of returning an error, so PR-Agent cannot detect that
boundary and switch models. Use OpenAI project budgets and usage alerts.

## Review behavior

The machine-facing review rubric lives in
`.agents/skills/draftly-code-review/SKILL.md`. PR-Agent loads only that skill;
it does not load the unrelated `avoid-ai-writing` skill. The rubric defines the
review procedure, Draftly-specific risk priorities, the threshold for an
actionable finding, and the required finding format. Its dedicated repository
context lives in `CODE_REVIEW_CONTEXT.md`.

PR-Agent does not inject `AGENTS.md` or `CLAUDE.md` into reviews. Those files
remain focused on implementation agents, while the review context contains only
the repository facts and invariants needed to assess a pull request.

Keep review behavior in the skill instead of duplicating it in `AGENTS.md`,
`CLAUDE.md`, or this runbook. `.pr_agent.toml` is the single home for the model,
limits, and feature flags; the workflow no longer sets them, so there is one
place to change and no dead configuration. `AGENTS.md` and `CLAUDE.md` remain
the source for implementation rules that apply to every coding agent. Numerical
scores remain disabled, and each review returns at most five findings.

`require_can_be_split_review` and `require_ticket_analysis_review` are off.
Both emit their own sections, which bypass the skill's finding threshold and
produce the vague suggestions it forbids. Turn ticket analysis back on only
after a PR-to-Linear linking convention is documented here.

### Confirming that the rubric loaded

The rubric and the repository context load through two different mechanisms —
`skills.paths` in the workflow, and `repo_context_files` in `.pr_agent.toml` —
and each can fail silently, leaving a review that looks normal but was not
governed by these rules. PR-Agent renders a fixed review schema and discards
extra model text, so a confirmation footer in the model response is not a
reliable signal.

After changing review configuration, inspect one live Actions run. The
`Run PR-Agent review` log must show all of the following:

- `Generating prediction with gpt-5.4-mini`
- an `Organizational standards and review skills` prompt section containing
  `### Skill: draftly-code-review`
- a repository-context section containing
  `<file path="CODE_REVIEW_CONTEXT.md" scope="repo-root">`
- no `Skills path does not exist` warning

Discard the review and fix the configuration if any of those checks fail.

### What is and is not protected

The workflow checks out the default branch before running PR-Agent, so the
rubric and `.pr_agent.toml` used at review time are the merged ones.

| Artifact | Read from | A pull request can change it? |
| --- | --- | --- |
| `.agents/skills/draftly-code-review/SKILL.md` | Default branch | No |
| `CODE_REVIEW_CONTEXT.md` | Default branch | No |
| `.pr_agent.toml` | Default branch checkout | No |
| `.github/workflows/pr-agent.yml` | **The pull-request head** | **Yes** |

The last row is the real limit. On a same-repo pull request GitHub runs the
workflow definition from the PR branch, so a pull request can repoint
`skills.paths`, remove a step, or add one that reads `OPENAI_KEY`. The
default-branch checkout cannot prevent that, because the code choosing what to
check out is itself the untrusted file.

Until branch protection and CODEOWNERS are enforceable on this plan, the
mitigation is the `guard-review-config` job: any pull request touching
`.github/`, `.agents/`, `.pr_agent.toml`, or `CODE_REVIEW_CONTEXT.md` fails
unless its author appears in the repository variable
`REVIEW_CONFIG_MAINTAINERS`. That job is advisory in the same sense the review
is — it is not a required check until the plan upgrade — but it makes the change
loud rather than silent.

Consider also moving `OPENAI_KEY` into a GitHub Environment with required
reviewers, so a workflow edit cannot reach the secret without a human approval.

## Trigger policy

Automatic review runs when a **non-draft** pull request is:

- Opened or reopened
- Marked ready for review
- Assigned or re-assigned for review

Draft pull requests are excluded. Without that filter a draft is reviewed on
`opened` and again on `ready_for_review`, paying twice for feedback the author
has not asked for yet.

It does not rerun automatically for every pushed commit. After addressing
feedback, a trusted collaborator can comment:

```text
/review
```

Use the high-reasoning command only when the change meets the sensitive or
critical threshold.

The comment must match one of those two strings exactly after trimming
whitespace. This is deliberate: accepting any comment starting with `/review`
would let a collaborator append `--config.extra_instructions=...` and rewrite
the rubric from a comment box. Add a new command by adding it to the allowlist
in the workflow, not by loosening the match. `/review` on a closed or merged
pull request is ignored.

## Privacy and secrets

The review request can include source code, diffs, filenames, pull-request
text, issue context, and selected repository guidance. Never commit or send:

- Real client names, NICs, addresses, or matter identifiers
- Deeds, title documents, pedigree chains, or private legal instructions
- Production logs or database exports
- `.env` files, API keys, passwords, tokens, or credentials
- Quarantined corpus content or proprietary reference assets

Create a dedicated OpenAI project for this workflow:

```text
draftly-code-review
├── Dedicated API key
├── Project budget and usage alerts
├── GitHub PR-Agent access only
└── No production legal-document access
```

If complimentary usage requires shared API inputs and outputs, the team must
explicitly approve sharing the private source code. Disable sharing before the
repository contains commercially sensitive or client-derived material.

Store the API key as the repository Actions secret `OPENAI_KEY`. Never place it
in `.pr_agent.toml`, workflow source, logs, or repository variables.

## GitHub and merge policy

The workflow has only the permissions required to read repository content and
publish pull-request feedback. `ci.yml` is `contents: read` only. The
third-party PR-Agent action is pinned to an immutable commit rather than a
movable branch or tag.

The PR-Agent step runs with `continue-on-error: true`. AI review is advisory and
there is deliberately no fallback model, so a provider outage must not present
as a code failure on the pull request.

This private organization repository currently uses GitHub Free, so native
branch protection cannot enforce the review or CI result. After upgrading the
organization plan, protect `main` with:

- Pull requests required
- Existing `CI / verify` check required
- One human approval required
- Stale approvals dismissed after new changes
- Conversations resolved before merge
- Force pushes and branch deletion disabled
- Administrators included in enforcement

AI feedback is never a substitute for that human approval.

## Configuration files

- `.pr_agent.toml` contains the model, reasoning effort, limits, feature flags,
  skill token budget, and the `repo_context_files` pointer. It is the only place
  those are set; the workflow no longer duplicates them.
- `.agents/skills/draftly-code-review/SKILL.md` contains the machine-facing
  Draftly review rubric, including the injection rule and the confirmation line.
- `CODE_REVIEW_CONTEXT.md` contains the reviewer's repository context and
  invariants and is loaded through `config.repo_context_files`. It covers the
  five backend cross-cutting documents, the precedence rule between them and a
  service plan, and the mechanical registry checks.
- `.github/workflows/pr-agent.yml` contains trusted triggers, permissions,
  pinned actions, the draft and comment filters, the `guard-review-config` job,
  and the default-branch skill path.
- `.github/workflows/ci.yml` remains the deterministic build gate. It runs the
  frontend gates and markdown lint today, validates
  `backend/contracts/services.yaml`, and enables the backend gates
  automatically once `backend/pyproject.toml` exists.

The rubric and the review context are linted. Only the vendored
`avoid-ai-writing` skill is excluded from `pnpm check:markdown`, because a
parser reads the rubric and its formatting matters more than most files here.

## Required setup

1. Create the dedicated OpenAI project and API key.
2. Confirm whether the OpenAI organization is eligible for complimentary
   shared-traffic tokens before enabling data sharing.
3. Set a project budget and usage alerts even when complimentary usage applies.
4. Add the key at **Repository Settings → Secrets and variables → Actions** as
   the secret `OPENAI_KEY`.
5. Add the repository **variable** `REVIEW_CONFIG_MAINTAINERS` in the same
   place: a comma-separated list of GitHub logins allowed to change review
   configuration. `guard-review-config` fails closed until this exists.
6. Confirm that `config.repo_context_files` and
   `config.repo_context_from_default_branch` are recognised keys in the pinned
   PR-Agent commit. PR-Agent uses dynaconf, which accepts unknown keys silently,
   so an unsupported key means the context is not loaded and nothing reports it.
   Step 8 is the check that catches this.
7. Open a small test pull request and verify one automatic review.
8. **Confirm the review ends with `draftly-code-review v1 · context: loaded`.**
   A missing line means the skill did not load; `context: missing` means the
   repository context did not. Do not treat the pipeline as working until this
   line is correct.
9. Comment `/review` and verify a trusted manual rerun.
10. Run the sensitive command and confirm that logs show `gpt-5.4-mini` with
    `high` reasoning.
11. Open a throwaway pull request that edits `.pr_agent.toml` from a
    non-maintainer account and confirm `guard-review-config` fails it.

## Maintenance

- Review model selection and complimentary-token eligibility monthly.
- Update the pinned PR-Agent commit deliberately after reviewing its release,
  and re-verify the confirmation line afterwards — a settings-key rename in an
  upstream release is exactly the silent breakage that line exists to catch.
- Pin `pnpm/action-setup` in `.github/workflows/ci.yml` to an immutable commit
  SHA. It is a third-party action on a movable tag while PR-Agent is pinned;
  the inconsistency is not deliberate.
- Re-check `max_model_tokens` against the model's real context window. Set too
  low, a large diff is compressed and files are dropped silently; the skill's
  truncation-disclosure rule mitigates that but does not remove it.
- Test model changes against representative historical Draftly pull requests.
- Measure useful findings, false positives, latency, and cost instead of
  assuming that a newer or higher-effort model is automatically better.
- Remove PR-Agent if the community-maintained project no longer receives
  acceptable security or compatibility updates.

## References

- [OpenAI model selection](https://developers.openai.com/api/docs/models)
- [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [OpenAI data sharing and complimentary tokens](https://help.openai.com/en/articles/10306912-sharing-feedback-evaluation-and-fine-tuning-data-and-api-inputs-and-outputs-with-openai)
- [PR-Agent automation configuration](https://github.com/The-PR-Agent/pr-agent/blob/main/docs/docs/usage-guide/automations_and_usage.md)
- [PR-Agent agent skills](https://github.com/The-PR-Agent/pr-agent/blob/main/docs/docs/core-abilities/agent_skills.md)
- [GitHub Actions security guidance](https://docs.github.com/en/actions/reference/security/secure-use)
