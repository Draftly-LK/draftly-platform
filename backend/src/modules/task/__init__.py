"""task — compiled checklists, item state, and satisfaction decisions.

Owns the runtime side of the checklist: the versioned snapshot a matter is being
worked under, each item's seven orthogonal statuses, and the many-to-many links
between items and the documents offered to satisfy them.

It does not own the requirement *definitions* (content_governance), the evidence
(document), or the facts (verification).
"""
