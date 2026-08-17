"""check — deterministic cross-document checks and the legal issues they raise.

Owns two records: the immutable `CrossDocumentCheck` result, pinned to the rule
version and the exact fact versions it read, and the mutable `LegalIssue` a
failure or an inconclusive comparison creates.

It owns neither the check *definitions* (content_governance), the facts
(verification), nor the evidence (document). A result here says the encoded
comparison passed or failed; it is never a title opinion, and an accepted risk
never rewrites one (§7.1, §7.3).
"""
