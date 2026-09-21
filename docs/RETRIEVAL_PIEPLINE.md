# Query rewriting over hybrid statutory retrieval

Implementation specification for adding an LLM query-rewrite stage in front of
the existing three-channel hybrid retriever (BM25 lexical, dense embeddings,
statutory graph expansion) fused with reciprocal rank fusion.

Status of this document: design only. Nothing here has shipped. Every number
quoted from an experiment is measured against proposed gold that no lawyer has
adjudicated, so none of it is a validated quality claim.

Audience: the engineer or agent implementing the change. Read `CLAUDE.md` and
the "Statute retrieval engine" section of `README.md` first; this document
assumes both.

## 1. Scope

In scope:

- A new `rewrite` stage that turns a lawyer's question (everyday wording, often
  with a factual scenario attached) into a dense statutory-vocabulary search
  string.
- Wiring that string into `src/draftly/retrieval/search.py` as additional ranked
  lists for the existing RRF fusion, alongside the untouched original-query
  channels.
- A citation-injection guard so a rewrite can never introduce an Act title,
  section number or `SRC` identifier that the user did not write.
- Caching, configuration, degradation, evaluation and tests for the above.

Out of scope:

- Changing corpus scope. `ALLOWED_KINDS`, the two runtime checks in
  `corpus.py`, the schema `CHECK (kind IN ('statute', 'amendment'))` in
  `index.py` and the answering prompt stay exactly as they are. This change
  touches querying only.
- Changing `answering.py`'s citation gate, entailment verifier or its existing
  post-hoc corrective retry. Section 11 covers how the two rewrite paths
  coexist.
- Retraining or swapping the dense embedding model.
- Anything that would let generated text reach a user as verified legal fact.
  Retrieval output stays `status=unverified`.

## 2. Why this stage, and what the evidence actually supports

The missing-edge experiment (`experiments-missing-edge/`,
`scripts/missing-edge/pilot_systems.py`) ran an LLM query rewrite as system
`A5_rewrite` against the hybrid RRF reference `S4_hybrid_rrf`. On the primary
KEEP stratum of the test split (19 questions, 14 matters) it was the only
variant that beat the reference on complete-bundle retrieval:

| System | C@20 | R@20 | Delta C@20 vs S4 |
| --- | ---: | ---: | --- |
| A5 rewrite | 0.393 | 0.488 | +0.143, CI95 [+0.000, +0.357] |
| A9 CQCR | 0.286 | 0.375 | +0.036, CI95 [-0.107, +0.214] |
| S4 hybrid RRF | 0.250 | 0.363 | reference |
| S1 BM25 | 0.143 | 0.250 | -0.107 |
| S3 dense only | 0.143 | 0.331 | -0.107 |
| S5 hybrid + cross-encoder rerank | 0.107 | 0.214 | -0.143 |

Source: `experiments-missing-edge/test-scores.json` and
`paper/figures/t2_main.tex`.

Four things about that table constrain this design:

1. The confidence interval's lower bound sits at 0.000. The effect is
   suggestive, not established, and the sample is 14 matters.
2. `A5_rewrite` was near-worst on the dev split and best on test
   (`scripts/missing-edge/make_brief.py:168`). Treat the size of the effect as
   unknown and the sign as plausible.
3. The gold set is agent-produced with zero lawyer approval. The integrity
   audit for that experiment returned WARN on exactly this point
   (`experiments-missing-edge/EXPERIMENT_AUDIT.md`).
4. The experiment ran on a separate research retriever
   (`scripts/statutory-qa/sq_retrieval.py`), not on the production engine this
   spec targets. The two differ in embedding model, field weighting and
   expansion mechanics, so the result does not transfer automatically.

The implication for rollout: build the stage behind a flag that defaults to
off, then decide with the gates in section 13. Do not ship it on by default on
the strength of the table above.

## 3. Where the code goes

Target package: `src/draftly/retrieval/` (the production engine). Do not build
this inside `scripts/`; the experiment code there is a frozen research artifact
and rerunning it must stay byte-reproducible.

New files:

| Path | Purpose |
| --- | --- |
| `src/draftly/retrieval/rewrite.py` | Rewrite generation, sanitisation, cache |
| `tests/test_statute_rewrite.py` | Unit tests for the above |

Modified files:

| Path | Change |
| --- | --- |
| `src/draftly/retrieval/models.py` | Add `RewriteResult`; add `rewrite` field to `StatuteQuery` |
| `src/draftly/retrieval/search.py` | Add rewrite channels to the fusion input |
| `src/draftly/retrieval/paths.py` | Add `REWRITE_CACHE_DB` |
| `src/draftly/retrieval/__main__.py` | Add `--rewrite` / `--no-rewrite` to `search` and `ask`, add a `rewrite` subcommand for inspection |
| `src/draftly/retrieval/api.py` | Accept and echo the rewrite flag; expose the rewrite in the response trace |
| `README.md` | Record the new stage and its default in the pipeline status table |

Existing anchors the implementation depends on:

- `search.py:120` `search()` is the single entry point. All fusion input is
  assembled in the `ranked_lists` list of `(label, hits, weight)` tuples.
- `search.py:225` `fuse_rankings()` is the RRF implementation, `RRF_K = 60`.
- `search.py:266` `direct_lookup()` resolves explicit section references and
  Act titles at score `-100.0`, which `fuse_rankings` turns into a `+0.05`
  bonus. This function must never see rewritten text. See section 8.
- `search.py:298` `lexical_lookup()` is the BM25 channel (FTS5, field weights
  `4.0 / 3.0 / 1.0` over title, heading, body).
- `embeddings.py:172` `dense_lookup()` is the dense channel.
- `graph.py:131` `expand_seeds()` is the personalized-PageRank expansion.
- `answering.py:295` `generate_json()` is the structured Gemini call with
  retry and quota backoff. Reuse it rather than writing a second client.

## 4. Pipeline

```text
StatuteQuery(text, topic_slug, kinds, source_id, limit, rewrite)
  |
  +-- analyze_question(text)            existing: subquestions, subqueries, source hints
  |
  +-- rewrite stage                     NEW (bounded, cached, optional)
  |     for each of the first N subqueries (N = DRAFTLY_REWRITE_MAX_PARTS):
  |       cache lookup on (prompt_version, model, sha256(subquery))
  |       miss -> one generate_json() call -> sanitise -> store
  |     -> tuple[RewriteResult, ...]
  |
  +-- channel assembly (search.py)
  |     original query:  direct_lookup + lexical_lookup      weight 1.00
  |     original query:  dense_lookup                        weight 1.00
  |     source-hinted lexical                                weight 1.35
  |     curated seeded entry points                           weight 1.80
  |     rewritten query: lexical_lookup                      weight 1.00   NEW
  |     rewritten query: dense_lookup                        weight 1.00   NEW
  |
  +-- fuse_rankings(...)                 RRF, k = 60
  |
  +-- expand_seeds(top fused hits)       graph channel        weight 0.90
  |
  +-- fuse_rankings(...) -> list[StatuteHit]
```

Two properties of this shape matter and must survive review:

- The rewrite adds channels, it does not replace the original query. The A5
  experiment replaced the query text outright
  (`pilot_systems.py:233`). Replacement discards the lexical signal from any
  term the lawyer wrote and the model dropped, which on this corpus includes
  exact statutory nouns that BM25 handles well. Fusing keeps both. Both
  behaviours are implemented; see `DRAFTLY_REWRITE_MODE` in section 9. The
  default is `fuse`, and `replace` exists so the experiment's configuration can
  be reproduced exactly on the same harness.
- Graph expansion runs after fusion, on the fused seeds, unchanged. Rewrite
  hits therefore feed the graph walk without any new code in `graph.py`.

## 5. Module contract: `rewrite.py`

```python
"""LLM query rewriting for the statute retrieval engine.

The rewrite is a SEARCH STRING, never an answer and never an authority. It is
sanitised before use (no Act titles, no section numbers, no SRC ids) and is
only ever passed to the lexical and dense channels, never to direct_lookup.
"""

PROMPT_VERSION = "rewrite-v1"

@dataclass(frozen=True)
class RewriteResult:
    original: str            # the subquery as written by the caller
    rewritten: str           # sanitised rewrite; "" when unavailable
    prompt_version: str
    model: str
    cached: bool
    removed_spans: tuple[str, ...] = ()   # what the guard stripped, for the trace
    reason: str = ""         # why rewritten is empty, when it is

    @property
    def usable(self) -> bool: ...


def rewrite_queries(
    subqueries: Sequence[str],
    *,
    background: str = "",
    max_parts: int | None = None,
    enabled: bool | None = None,
) -> tuple[RewriteResult, ...]:
    """Rewrite up to max_parts subqueries. Never raises.

    Returns one RewriteResult per input subquery, in input order, with
    unrewritten tails carrying rewritten="" and reason="over_part_budget".
    """


def rewrite_one(text: str, *, background: str = "") -> RewriteResult:
    """Single rewrite. Cache hit, cache miss with one bounded LLM call, or an
    empty result. Never raises."""


def sanitize_rewrite(rewritten: str, original: str) -> tuple[str, tuple[str, ...]]:
    """Strip citation-shaped spans the user did not write.
    Returns (clean_text, removed_spans)."""


def rewrite_status() -> dict[str, object]:
    """Diagnostics for the CLI and API: model, prompt version, cache path,
    cached entries, availability. Mirrors embeddings.embedding_status()."""
```

Hard requirements on this module:

- No exception escapes `rewrite_queries`, `rewrite_one` or `sanitize_rewrite`.
  Every failure path returns an empty rewrite with a populated `reason`. The
  engine must degrade to today's behaviour, exactly as the dense channel does
  when `GEMINI_API_KEY` is absent (`embeddings.py:46`).
- No network call when the cache hits, and no network call at all under
  `DRAFTLY_REWRITE_CACHE_ONLY=1`.
- Temperature 0. The rewrite is part of a retrieval index path; two identical
  queries must produce identical rankings within a cache generation.
- The module never imports from `answering.py` at module scope beyond
  `generate_json`, to keep the import graph acyclic.

### Changes to `models.py`

Add one field to `StatuteQuery`, defaulting to `None` so every existing
construction site keeps working:

```python
@dataclass(frozen=True)
class StatuteQuery:
    text: str
    topic_slug: str | None = None
    kinds: tuple[str, ...] | None = None
    source_id: str | None = None
    limit: int = 8
    rewrite: bool | None = None   # None -> DRAFTLY_REWRITE env default
```

`StatuteHit.matched_queries` already records which query produced a hit and is
already surfaced through `to_dict()`. Rewrite channels must label their ranked
lists so a rewrite-sourced hit is visibly attributed, for example
`f"rewrite: {result.rewritten[:60]}"`. This is the user-facing audit trail for
the stage and is not optional.

## 6. Prompt and response schema

Use the prompt that produced the measured result, adapted from
`scripts/missing-edge/gen_queries.py:40` so the production path is comparable
to the experiment. Keep it verbatim in wording, including the three
prohibitions, and keep it in `rewrite.py` as a module constant next to
`PROMPT_VERSION`.

```text
You are helping search a Sri Lankan statute book.

Rewrite the question below as a single dense search query. Replace everyday
words with the formal statutory terms Sri Lankan legislation would use, and name
every legal concept, instrument, requirement and actor that the answer would
have to rely on. Do NOT name specific Act titles, Act numbers or section
numbers. Do NOT answer the question.

Output ONLY the rewritten query as one paragraph, no preamble.

SCENARIO:
{background}

QUESTION:
{question}
```

Call it through `answering.generate_json()` with this schema, rather than
parsing free text:

```python
REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"rewritten_query": {"type": "string"}},
    "required": ["rewritten_query"],
}
SYSTEM_INSTRUCTION = (
    "You rewrite legal research questions into statute-search queries. "
    "You never name Acts or section numbers and you never answer the question."
)
```

Bounds:

- `background` truncated to 6000 characters, as in the experiment.
- Response truncated to 1500 characters after whitespace collapse, as in the
  experiment (`gen_queries.py:90`).
- `tries=2` on `generate_json`. The answering path already absorbs quota
  failures with long backoff; a retrieval-time rewrite should give up fast and
  fall through to the unrewritten query rather than stall a search.

Model: `DRAFTLY_REWRITE_MODEL`, defaulting to the value of
`DRAFTLY_GEMINI_MODEL` (itself defaulting to `gemini-3.5-flash`,
`answering.py:16`). For reproducing the experiment exactly, the A5 numbers were
produced by `nvidia/nemotron-3-super-120b-a12b` at temperature 0 through
`scripts/missing-edge/llm.py`. If that comparison is needed, add an NVIDIA
transport behind the same `rewrite_one` contract rather than changing the
contract.

Prompt changes bump `PROMPT_VERSION`, which is part of the cache key. Never
edit a prompt in place without the bump; stale cached rewrites under a changed
prompt would silently mix two systems in one evaluation run.

## 7. Multi-part questions

`analyze_question()` already splits a multi-part exam question into
`subqueries` (`question_analysis.py`, `QuestionAnalysis.subqueries`), and
`search()` iterates the first eight of them (`search.py:133`). Each part is a
distinct legal issue, so each part gets its own rewrite.

Bound the cost: rewrite at most `DRAFTLY_REWRITE_MAX_PARTS` subqueries,
default 4, in the order `analyze_question` returned them. Parts beyond the
budget keep their original-query channels only and their `RewriteResult`
carries `reason="over_part_budget"`.

The subquery strings that `search()` builds can carry a `" Context:"` suffix;
`search.py:150` already splits it off for the source-hint pass. Rewrite the
issue text, not the concatenation: pass `subquery.split(" Context:", 1)[0]` as
the question and the remainder as `background`.

## 8. Citation-injection guard

This is the correctness-critical part of the change. Read it before writing any
fusion code.

`direct_lookup()` resolves an Act title plus a section number, or a bare
`SRC001:s2`, into a hit at score `-100.0`, and `fuse_rankings()` gives such
hits an extra `+0.05` (`search.py:237`). A hallucinated pairing such as
"section 7 of the Notaries Ordinance" appearing in a rewrite would therefore be
promoted to or near the top of the result list as if the lawyer had asked for
it by name. On a legal drafting product that is the worst available failure
mode: fabricated authority presented as a direct lookup.

Two independent defences, both required:

**Structural.** The rewrite is passed only to `lexical_lookup()` and
`dense_lookup()`. `direct_lookup()`, `seeded_source_hits()` and the
`SOURCE_HINT_TERMS` pass keep receiving user text only. Enforce this by
construction: build the rewrite channels from a `StatuteQuery` produced by
`replace(query, text=result.rewritten)` that is passed to those two functions
and nothing else, and assert the invariant in a test.

**Lexical.** `sanitize_rewrite()` strips, from the rewrite, any span that
looks like a citation and is not present in the original text:

1. `search.SECTION_ID_RE` matches, for example `SRC001:s2`.
2. `search.SOURCE_ID_RE` matches, for example `SRC034`.
3. `search.SECTION_REF_RE` matches, for example `section 7`, `s.7`, `s 7A`.
4. `search.SECTION_RANGE_RE` matches, for example `sections 22 to 26`.
5. Any Act title from `corpus.sources_for_ui()` that appears in the rewrite
   (case-insensitive) and does not appear in the original text.

Reuse the compiled patterns from `search.py`; do not restate them in
`rewrite.py`, or the two copies will drift. If that creates an import cycle,
move the four patterns into a new `src/draftly/retrieval/patterns.py` and
import from both. Prefer the move.

After stripping, collapse whitespace and apply a floor: if the remaining text
has fewer than four non-stopword tokens (reuse `search.STOPWORDS` and
`search.TOKEN_RE`) or fewer than 20 characters, discard the rewrite entirely
and return `reason="degenerate_after_sanitize"`. A near-empty rewrite fed to
BM25 produces noise, and noise that gets an RRF weight is worse than nothing.

Every removed span goes into `RewriteResult.removed_spans` and into the trace.
A model that repeatedly tries to name Acts despite the prompt is a signal worth
seeing in the logs, not a silent correction.

## 9. Configuration

All flags are read at call time, not import time, so tests can set them with
`unittest.mock.patch.dict(os.environ, ...)`.

| Variable | Default | Effect |
| --- | --- | --- |
| `DRAFTLY_REWRITE` | `0` | Master switch. `0` reproduces today's engine exactly |
| `DRAFTLY_REWRITE_MODE` | `fuse` | `fuse` adds rewrite channels; `replace` swaps the original query text for the rewrite in the lexical and dense channels, matching the A5 experiment |
| `DRAFTLY_REWRITE_MODEL` | value of `DRAFTLY_GEMINI_MODEL` | Rewrite model |
| `DRAFTLY_REWRITE_MAX_PARTS` | `4` | Upper bound on LLM calls per `search()` |
| `DRAFTLY_REWRITE_WEIGHT_LEXICAL` | `1.0` | RRF weight for the rewritten lexical list |
| `DRAFTLY_REWRITE_WEIGHT_DENSE` | `1.0` | RRF weight for the rewritten dense list |
| `DRAFTLY_REWRITE_CACHE_ONLY` | `0` | `1` forbids network calls; cache hit or no rewrite. Use in CI |
| `DRAFTLY_REWRITE_TIMEOUT_MS` | `20000` | Per-call timeout, passed through to `generate_json` |

`StatuteQuery.rewrite` overrides `DRAFTLY_REWRITE` per query. Precedence:
explicit `StatuteQuery.rewrite`, then the environment, then off.

The existing ablation switches keep working and compose with the new ones:
`DRAFTLY_DISABLE_DENSE`, `DRAFTLY_DISABLE_GRAPH`, `DRAFTLY_SKIP_CORRECTIVE`.
A rewrite run with `DRAFTLY_DISABLE_DENSE=1` must still work and fall back to
rewrite-lexical only.

## 10. Fusion changes in `search.py`

Insert the rewrite channels inside the existing `for subquery in
subqueries[:8]` loop, after the dense block at `search.py:145`, so a rewrite
sits next to the channels for the same part:

```python
rewrite_result = rewrites.get(subquery)          # precomputed before the loop
if rewrite_result is not None and rewrite_result.usable:
    label = f"rewrite: {rewrite_result.rewritten[:60]}"
    rewritten_query = replace(scoped, text=rewrite_result.rewritten)

    rewrite_lexical = lexical_lookup(conn, rewritten_query, exclude=set())
    if rewrite_lexical:
        ranked_lists.append((label, rewrite_lexical, REWRITE_WEIGHT_LEXICAL))

    if os.getenv("DRAFTLY_DISABLE_DENSE", "0") != "1":
        rewrite_dense = hits_for_ids(
            conn, dense_lookup(rewrite_result.rewritten, limit=12), rewritten_query
        )
        if rewrite_dense:
            ranked_lists.append((label, rewrite_dense, REWRITE_WEIGHT_DENSE))
```

Rules for this edit:

- Compute all rewrites in one batch before opening the SQLite connection. Do
  not hold a connection open across network calls.
- `exclude=set()`, not the direct-hit exclusion used for the original query.
  The rewrite channel is an independent ranking; RRF handles the overlap, and
  passing an exclusion set would distort its ranks.
- `replace(scoped, text=...)` preserves `topic_slug`, `kinds` and `source_id`,
  so every hard filter the caller asked for still applies to rewrite hits.
  `row_allowed()` re-checks them anyway; keep both.
- `make_excerpt()` is called with the rewrite text for rewrite-sourced hits,
  which would centre the excerpt on model wording rather than the lawyer's.
  Avoid that: after fusion, rebuild the excerpt for every returned hit from the
  original `query.text`. The cheapest correct place is `fuse_rankings()`, which
  already rewrites each hit with `replace(...)`; add `excerpt=make_excerpt(
  hit.text, original_text)` there and pass the original text in. Without this,
  a user sees a snippet chosen by the rewrite, which is misleading about why the
  section was returned.
- Under `DRAFTLY_REWRITE_MODE=replace`, skip the original-query lexical and
  dense channels for any part that has a usable rewrite, and keep
  `direct_lookup` on the original text regardless. Replace mode never becomes a
  route for unsanitised text to reach a direct lookup.

`RRF_K` stays 60. Do not retune it in this change; it is shared with every
other channel and a single change with two moving constants is not
attributable.

## 11. Interaction with the existing corrective retry

`answering.py` already rewrites queries once, after generation, for any answer
part left unverified (`answering.py:506` `corrective_retry`, prompt at
`answering.py:528`). That loop is post-hoc and verification-driven; this stage
is pre-retrieval and unconditional. They are complementary and both stay.

Required behaviour:

- `corrective_retry` keeps calling `search()`. When `DRAFTLY_REWRITE=1`, the
  corrective queries get rewritten too. That is acceptable and cheap because of
  the cache, but it must be bounded: pass `rewrite=False` on the
  `StatuteQuery` objects built inside `corrective_retry`, because those strings
  are already model-generated statutory-vocabulary queries. Rewriting a rewrite
  adds cost and drift for no signal.
- `StatuteAnswer.retrieval_queries` must record the rewrites actually used, so
  the answer trace shows every string that influenced retrieval. Extend the
  tuple rather than adding a field.
- Keep `DRAFTLY_SKIP_CORRECTIVE` semantics unchanged.

## 12. Cache

A separate SQLite file, not the fingerprinted index. Rewrites do not depend on
the corpus, so an index rebuild must not invalidate them.

Add to `paths.py`:

```python
REWRITE_CACHE_DB = INDEX_DIR / "query-rewrites.sqlite"
```

Schema:

```sql
CREATE TABLE IF NOT EXISTS rewrites (
    prompt_version TEXT NOT NULL,
    model          TEXT NOT NULL,
    query_sha256   TEXT NOT NULL,
    original       TEXT NOT NULL,
    rewritten      TEXT NOT NULL,
    removed_spans  TEXT NOT NULL,   -- JSON array
    created_at     TEXT NOT NULL,   -- ISO 8601 UTC
    PRIMARY KEY (prompt_version, model, query_sha256)
);
```

`query_sha256` is `sha256(f"{background}\n\n{question}")` over the truncated,
whitespace-collapsed inputs, so the key covers everything the prompt sees.

Behaviour:

- Store the sanitised rewrite, and store `""` for a rewrite that sanitised to
  nothing, so a degenerate result is not re-requested on every search.
- Do not cache transport failures. A quota error must not become a permanent
  empty rewrite for that query.
- The file is generated, reproducible and not a corpus artifact. Add
  `data/processed/retrieval-indexes/**/query-rewrites.sqlite` to `.gitignore`
  if the index directory is not already ignored wholesale; check before adding
  a redundant rule.
- No pruning in this change. Record the row count in `rewrite_status()` and
  revisit if it grows past a few tens of thousands.

## 13. Evaluation plan

Three harnesses already exist. Use all three, and report all three even when
one moves the wrong way.

**Primary regression check: LSR.** `uv run python -m draftly.retrieval
evaluate-lsr`, 462 queries derived from verified case-to-statute links. Current
baseline, from `evaluation/runs/statute-retrieval-lsr-v1/metrics.json`: overall
recall@5 0.2056, recall@10 0.2381, MRR 0.1478, nDCG@10 0.1694, with the
`applicable` and `superseded-since-judgment` strata reported separately. This
is the largest honest set in the repo and the rewrite must not degrade it.

Note the prompt mismatch before reading those results: LSR queries are masked
judgment paragraphs, not a scenario plus a question. Pass the paragraph as
`question` and leave `background` empty, and expect a smaller effect here than
the exam-question setting the prompt was written for. Say so in the run notes
rather than explaining it away afterwards.

**Secondary: the ten-row dev set.** `evaluate` writes to
`evaluation/runs/statutes-bm25-v1/`. Ten unverified labels cannot support a
conclusion; use it as a smoke check that nothing collapsed.

**Secondary: the questions harness.** `evaluate-questions` over
`src/questions.md`, retrieval-only mode first. This is the multi-part exam
shape the rewrite prompt was written for, so it is where an effect is most
likely to show.

Run layout, following the existing convention of one directory per run with
`config.json`, `metrics.json`, `predictions.csv`, `per-question-scores.csv`:

- `evaluation/runs/statute-retrieval-lsr-v2-rewrite/`
- `evaluation/runs/statutes-rewrite-v1/`

`config.json` must record `DRAFTLY_REWRITE`, `DRAFTLY_REWRITE_MODE`,
`PROMPT_VERSION`, the rewrite model, the channel weights, the corpus
fingerprint and the cache row count at run start. A run whose configuration
cannot be reconstructed from its own directory is not evidence.

For any A/B claim, reuse the metric implementations already in the repo rather
than writing new ones: `scripts/statutory-qa/evaluate.py` for
complete-bundle metrics and `scripts/missing-edge/paired_keep.py` for the
paired bootstrap. Both are the code that produced the published numbers.

Gates for flipping `DRAFTLY_REWRITE` to `1` by default. All four must hold:

1. LSR overall recall@5 does not fall below baseline outside a paired bootstrap
   interval that includes zero. A drop is a blocker, not a trade.
2. The questions harness shows a positive point estimate on complete-evidence
   retrieval.
3. Zero citation-injection guard escapes across every evaluation run, measured
   as: no returned hit whose only supporting channel is a rewrite channel and
   whose section ID appears in a rewrite's `removed_spans`.
4. Median added latency per search stays inside the budget in section 15.

Until those hold, the stage ships off by default and the CLI flag is the only
way in. If the gates pass, the README pipeline table and the ablation env var
list both need updating in the same commit.

Honesty constraints that apply to everything written about this stage:

- Retrieval output is `status=unverified`. A rewrite does not change that.
- The A5 result rests on proposed gold with no lawyer adjudication. Never
  describe it as validated, and never restate the +0.143 delta without its
  interval.
- If an evaluation run regresses, report the regression with the numbers. Do
  not tune the gold, the metric or the question set to recover it.

## 14. Test plan

`unittest`, matching `tests/test_statute_retrieval.py`. No test may make a
network call: set `DRAFTLY_REWRITE_CACHE_ONLY=1` and either seed the cache
directly or monkeypatch `rewrite.rewrite_one`. Group the tests into commits by
concern, five or more per commit.

Commit 1, sanitiser and contract (`tests/test_statute_rewrite.py`):

1. `test_section_reference_is_stripped_when_absent_from_original`
2. `test_source_id_and_section_id_are_stripped`
3. `test_act_title_present_in_original_survives_sanitize`
4. `test_section_range_is_stripped`
5. `test_degenerate_rewrite_is_discarded_with_reason`
6. `test_removed_spans_are_reported`

Commit 2, cache and degradation:

1. `test_cache_hit_makes_no_model_call`
2. `test_cache_key_includes_prompt_version`
3. `test_missing_api_key_returns_empty_rewrite_not_exception`
4. `test_transport_failure_is_not_cached`
5. `test_cache_only_mode_never_calls_the_model`
6. `test_part_budget_caps_model_calls`

Commit 3, search integration (extend `tests/test_statute_retrieval.py` or a
new `tests/test_statute_rewrite_search.py`):

1. `test_rewrite_disabled_by_default_reproduces_baseline_ranking`
2. `test_rewrite_never_reaches_direct_lookup`
3. `test_rewrite_hits_are_labelled_in_matched_queries`
4. `test_rewrite_respects_topic_and_kind_filters`
5. `test_excerpt_is_built_from_the_original_query`
6. `test_replace_mode_keeps_direct_lookup_on_original_text`
7. `test_rewrite_composes_with_disable_dense_and_disable_graph`

Test 1 in commit 3 is the regression anchor: with `DRAFTLY_REWRITE=0`, the
ranking for a fixed query must be identical to the pre-change engine. Capture
that expected ranking before touching `search.py`.

Test 2 is the guard test. Assert it structurally, for example by patching
`search.direct_lookup` with a wrapper that records every `query.text` it sees
and asserting no recorded text equals a rewrite.

## 15. Latency, cost and failure modes

Budget per `search()` call with the rewrite on and the cache cold: at most
`DRAFTLY_REWRITE_MAX_PARTS` (4) sequential LLM calls. Target median added
latency under 2.5 seconds for a single-part query and under 6 seconds for a
four-part exam question, measured on a warm index. Cache hits add under 10 ms.
If the measured numbers are worse, reduce `DRAFTLY_REWRITE_MAX_PARTS` before
adding concurrency; parallel calls against a free-tier quota trade latency for
429s.

Cost per cold query is one short completion per part. The dense channel already
spends a Gemini embedding call per subquery at query time
(`embeddings.py:181`), so this roughly doubles per-query model calls on an
uncached search. Record it in the run config; do not leave it implicit.

| Failure | Detection | Behaviour |
| --- | --- | --- |
| No `GEMINI_API_KEY` | `generate_json` returns an error | Empty rewrite, `reason="no_api_key"`, search unchanged |
| Quota exhausted (429) | error text contains `429` or `RESOURCE_EXHAUSTED` | Empty rewrite, not cached, `reason="quota"` |
| Timeout | `generate_json` error | Empty rewrite, `reason="timeout"` |
| Malformed JSON | `parse_model_json` error | Empty rewrite, `reason="parse_error"` |
| Model answers instead of rewriting | Sanitiser strips citations; length floor | Rewrite discarded when degenerate, otherwise used as a search string only |
| Model names an Act | `sanitize_rewrite` removes it, span recorded | Rewrite used without the Act name; span visible in the trace |
| Cache file locked or corrupt | SQLite error | Empty rewrite, `reason="cache_error"`, search unchanged |

Observability: `rewrite_status()` in the CLI and the API status payload;
`removed_spans` counts aggregated per run into `metrics.json`; every rewrite
string that influenced a result present in `StatuteAnswer.retrieval_queries`
and in `StatuteHit.matched_queries`.

## 16. Work plan

Ordered, each step independently reviewable and each ending green.

1. Capture the baseline. Run `evaluate`, `evaluate-lsr` and
   `evaluate-questions` on the current engine and keep the run directories.
   Without this there is nothing to compare against later.
2. Move `SECTION_ID_RE`, `SOURCE_ID_RE`, `SECTION_REF_RE`,
   `SECTION_RANGE_RE`, `STOPWORDS` and `TOKEN_RE` into
   `src/draftly/retrieval/patterns.py`; re-import them in `search.py`. No
   behaviour change, tests still green.
3. Add `rewrite.py` with the sanitiser and the cache, no model call yet. Land
   commit 1 and commit 2 of the test plan.
4. Add the model call through `generate_json`, plus `rewrite_status()`.
5. Add `RewriteResult` and the `StatuteQuery.rewrite` field.
6. Wire the channels into `search.py` behind `DRAFTLY_REWRITE`, default off.
   Fix the excerpt source as described in section 10. Land commit 3.
7. Add the CLI and API surfaces: `--rewrite` / `--no-rewrite` on `search` and
   `ask`, a `rewrite` subcommand that prints a `RewriteResult` for one query,
   and `rewrite_status()` in the API status response. Pass `rewrite=False`
   inside `corrective_retry`.
8. Run the three harnesses with the flag on, write the two run directories,
   and evaluate the section 13 gates. Report the outcome whichever way it goes.
9. Only if the gates pass: flip the default, update the README pipeline table
   and the ablation env var list, and record the decision with the run IDs that
   support it.

Definition of done for the code, independent of the gates: with
`DRAFTLY_REWRITE=0` the engine is byte-identical in behaviour to today; with
`DRAFTLY_REWRITE=1` and no API key it is also identical; with the flag on and a
key present, every returned hit is attributable to a labelled channel and no
unsanitised text has reached a direct lookup.

## 17. Open questions

These need a decision during implementation and are worth raising rather than
guessing at:

- Whether `fuse` or `replace` mode is the right default if the dev numbers are
  close. The experiment measured `replace`; this spec defaults to `fuse` on
  reasoning about the lexical channel, which is an argument, not a measurement.
  Measure both before defaulting.
- Whether the rewrite should also feed the source-hint pass
  (`SOURCE_HINT_TERMS`, `search.py:156`). It currently does not, because that
  pass carries weight 1.35 and is curated. Leaving it on user text only is the
  conservative choice.
- Whether per-part rewriting or one whole-question rewrite retrieves better on
  multi-part exam questions. The experiment had one question per query, so this
  is unmeasured on either harness.

## 18. Related files

- `src/draftly/retrieval/search.py`, `embeddings.py`, `graph.py`, `index.py`,
  `answering.py`: the engine this extends.
- `scripts/missing-edge/pilot_systems.py`, `gen_queries.py`: the A5 rewrite as
  it was actually run.
- `scripts/statutory-qa/sq_retrieval.py`: the research retriever the A5 numbers
  were measured on, including its BM25F field weights and RRF implementation.
- `experiments-missing-edge/test-scores.json`,
  `experiments-missing-edge/EXPERIMENT_AUDIT.md`: the results and their audit.
- `evaluation/runs/statute-retrieval-lsr-v1/metrics.json`: the LSR baseline.
- `proj-docs/project Management/retrieval-engine-methodology.md`: the wider
  methodology record, referenced from the README.
