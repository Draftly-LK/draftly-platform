# Task 3 R1 transaction-scope regression packet

This focused packet mounts the actual facts screen, scope editor and API client
against synthetic HTTP fixtures using production-build assets. It repairs scope
review semantics; it adds no approved visual baseline or design iteration.

At 1024 × 768, both English and Sinhala cover stale, renewed and unavailable
transaction references. All six captures have zero root horizontal overflow and
zero axe serious/critical violations. Healthy synthetic renders have no page
errors, warnings or failed assets. Two expected HTTP503 console errors come from
the deliberately unavailable reference states.

| State | Verified behavior |
| --- | --- |
| Selected version1, returned version9 | Old displayed roles stay visible but disabled; saving is disabled; the localized current-scope review action is keyboard reachable with a visible 2px focus outline |
| Deliberate keyboard review | Enter loads the returned donor role, removes the old owner role and enables saving; focus returns to the transaction selector with a visible 2px outline |
| Selected transaction absent after failed read | Selection retains the synthetic transaction ID and displays a localized unavailable-reference label; save and renewal are disabled; it does not become New transaction |

The browser issued zero transaction mutation requests in the stale/unavailable
probes. Owning component/API-client tests separately exercise successful renewed
version9 saves, missing-reference recovery and 412 refusal followed by deliberate
review/retry. This browser packet does not prove backend persistence or submit the
final renewed mutation by keyboard.

AI screenshot critique: the Sinhala stale-state renewal label and outline fit
inside the existing panel, old disabled roles remain readable, and the warning
provides context above the action. Existing design tokens and Button styling are
preserved. Human Sinhala terminology and visual approval remain pending.

`synthetic-scope-measurements.json` contains exact state, locale, focus, font,
layout, axe, request and console observations. No real case data was accessed.
The earlier 14-state, 200% and static Lighthouse packet was not rerun; its scope,
human gate limits, existing search-name advisory and Node engine advisory remain
as documented in the parent checklist.
