"""Synthetic document bytes."""

from __future__ import annotations


def synthetic_pdf(pages: int = 2) -> bytes:
    """A structurally minimal PDF. Synthetic — no client content whatsoever."""
    body = b"".join(b"/Type /Page \n" for _ in range(pages))
    return b"%PDF-1.7\n" + body + b"%%EOF\n"
