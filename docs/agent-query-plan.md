  # Hybrid Statutory Query-Rewrite Implementation

  ## Summary

  Move the statute-search runtime from draftly-research into the existing backend research module, then add the optional LLM rewrite
  channel described in docs/RETRIEVAL_PIEPLINE.md.

  The first release exposes authenticated asynchronous search, not generated legal answers. Rewrite remains off by default and retrieval
  results remain explicitly unverified. Experimental scripts and evaluation datasets stay in draftly-research.

  ## Implementation Changes

  ### Retrieval runtime and corpus boundary

  - Place the engine under backend/src/modules/research/infrastructure/retrieval/, including corpus loading, indexing, BM25, embeddings,
    graph expansion, question analysis, models, and search.

  - Define LegalRetrievalPort and provider-neutral request/result DTOs in the research application layer. Application and API code must
    not import retrieval internals.

  - Import only the 75-document processed statute/amendment text release, filtered metadata, topic mappings, and checksums. Do not copy
    raw documents, case-law pipelines, Streamlit code, experiments, or unrelated research data.

  - Record the source repository revision and release fingerprint. Treat the imported corpus as an internal unverified release;
    production enablement requires the corpus-governance approval/signature gate.

  - Store generated indexes and caches below backend/.data/retrieval/, outside tracked source. Add NumPy as the only new runtime
    dependency required by the existing dense channel.

  - Preserve the existing corpus guards: 57 statutes, 18 amendments, allowed kinds, schema checks, content fingerprinting, and immutable
    source identifiers.

  ### Rewrite stage

  - Extract citation and token patterns into a shared retrieval patterns.py; both direct lookup and sanitisation use the same compiled
    patterns.

  - Add RewriteResult and StatuteQuery.rewrite: bool | None.
  - Implement bounded per-part rewriting with the specified prompt, rewrite-v1, temperature 0, 6,000-character background limit, 1,500-
    character output limit, two attempts, and at most four rewritten parts.

  - Use a narrow structured-generation adapter around the backend’s Google client. Missing credentials, unapproved provider data
    transfer, quota errors, timeouts, malformed output, and cache failures return an unusable RewriteResult; they never fail the search.

  - Strip introduced SRC identifiers, section references/ranges, and corpus Act titles. Discard rewrites shorter than 20 characters or
    four non-stopword tokens after sanitisation.

  - Call the rewriter before opening the retrieval SQLite connection. Rewrites may reach only lexical and dense lookup—never direct
    lookup, curated source hints, or seeded statutory entry points.

  - In fuse mode, retain original lexical/dense channels and add rewritten lexical/dense channels at weight 1.0. Preserve graph
    expansion after initial fusion and keep RRF_K=60.

  - Support replace only for reproducibility: replace original lexical/dense channels when a usable rewrite exists, while direct lookup
    still receives the original text.

  - Rebuild final excerpts from the lawyer’s original query and label rewrite-sourced matches in matchedQueries.
  - Keep source-hint analysis on user text and rewrite separate question parts rather than the whole multi-part question.

  ### Configuration, cache, and privacy

  - Add typed settings corresponding to DRAFTLY_REWRITE, mode, model, maximum parts, channel weights, cache-only mode, and timeout.
    Defaults are rewrite off, mode fuse, four parts, weights 1.0, and a 20-second timeout.

  - Add a separate LEGAL_RETRIEVAL_ENABLED deployment kill switch. When enabled, startup verifies the corpus manifest and prepares the
    index.

  - Permit explicit request-level rewrite=false to disable rewriting. rewrite=true may enable the experimental stage only when retrieval
    is enabled and provider-transfer policy permits it.

  - Disable rewrite and dense network calls when provider_data_approval is false; lexical/direct/graph retrieval continues.
  - Use a runtime-local SQLite rewrite cache keyed by tenant namespace, prompt version, model, and a hash covering normalized background
    and question.

  - Do not store the original question or background in the cache. Store only the sanitised rewrite, removed spans, reason, and creation
    time. Do not share cached entries across users.

  - Never log questions, rewrites, removed spans, excerpts, provider responses, or corpus passages. Log only job IDs, model/prompt
    versions, cache outcomes, timings, and aggregate removal counts.

  ## API and Job Contracts

  - Add authenticated POST /api/v1/research/search with a required Idempotency-Key.
  - Request fields use strict camelCase: query, optional topicSlug, kinds, sourceId, limit, and optional rewrite.
  - The endpoint checks research.enabled, reserves one research_queries.monthly unit, persists a user-scoped search job, and enqueues
    only the job ID through the outbox. Raw query text never enters the outbox payload.

  - Add GET /api/v1/research/search-jobs/{jobId}. It returns 404 for another user’s job and exposes the standard queued/running/
    succeeded/failed state.

  - A completed result contains:
      - status: "unverified" and the corpus release/fingerprint;
      - filtered statute hits with matchedQueries;
      - a trace containing rewrite mode, prompt/model versions, cache status, each RewriteResult, removed spans, and degradation
        reasons.

  - Consume reserved usage for every completed search, including an empty result or lexical-only degradation. Release the reservation
    when the job fails before producing a result.

  - Register the worker in the existing dispatcher and persist search jobs/results in a research migration. Queries and results are
    user-scoped records; retention hooks must be available for the future approved policy.

  - Add a backend CLI using the same port for local inspection: search with --rewrite/--no-rewrite, inspect one rewrite, and print
    rewrite/index status.

  - Update OpenAPI, contract fixtures, backend settings documentation, and the retrieval design to reflect the backend module paths and
    asynchronous API.

  - Do not expose the migrated legacy /answer API or move answering.py. Grounded answer composition remains owned by the future research
    application service; its corrective retry must later call this port with rewrite=False.

  ## Test and Evaluation Plan

  - Migration parity: with rewrite disabled, compare fixed-query rankings, filters, direct lookups, fingerprints, and excerpts against
    the source engine at the recorded revision.

  - Sanitiser tests cover introduced and user-supplied Act titles, section IDs, source IDs, section ranges, whitespace collapse,
    degeneracy, and reported removed spans.

  - Cache/degradation tests cover tenant isolation, prompt/model/background keys, cache hits without model calls, cache-only mode,
    missing provider approval/key, transport failures not being cached, malformed responses, and the four-part call budget.

  - Search tests prove rewritten text never reaches direct lookup or source hints, hard filters survive, graph/dense ablations compose
    correctly, labels and excerpts use the correct query, and both fuse and replace behave as specified.

  - API/security tests cover authentication, idempotency, entitlement and quota enforcement, user isolation, async job transitions,
    reservation consume/release, safe errors, and absence of raw queries from logs/outbox messages.

  - Run backend gates: uv lock --check, Ruff check/format check, strict mypy, pytest, OpenAPI contract tests, and Docker build.
  - Keep the three quality harnesses in draftly-research. A separate evaluation adapter calls the authenticated platform search API; no
  - Capture baseline and rewrite runs for the 462-query LSR set, ten-row smoke set, and multi-part questions set. Measure fuse and
    replace, citation-guard escapes, cache-hit/cold latency, model-call counts, and all existing retrieval metrics.

  - Rewrite remains off by default unless LSR recall@5 has no statistically supported regression, the questions harness improves
    complete-evidence retrieval, citation-injection escapes remain zero, and median added latency stays below 2.5 seconds for one part
    and 6 seconds for four parts.

  ## Assumptions and Defaults

  - The backend research module becomes the runtime owner; draftly-research remains the corpus-production and evaluation workspace.
  - Raw search is available to authenticated users with the paid research entitlement; it does not require a new role capability because
    it is a non-mutating corpus read.

  - The initial rewrite mode is fuse; replace is evaluation-only.
  - Rewriting is per subquery, does not affect curated source hints, and remains disabled by default regardless of implementation
    completion.

  - Existing unrelated changes in both working trees are preserved and excluded from this work.