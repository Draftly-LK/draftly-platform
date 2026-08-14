"""Deterministic local rasterization (document-processing.md §4).

pypdfium2 rather than PyMuPDF: PyMuPDF is AGPL-licensed, pypdfium2 is
BSD/Apache and already proven in the research repo's pipeline. Rendering is
local — no document bytes leave the machine at this stage — and the DPI is
recorded on every page so coordinate mapping stays exact if a box-producing
engine is added later (§6).
"""

from __future__ import annotations

import io

import pypdfium2 as pdfium

from src.modules.document.domain.errors import UnsupportedDocumentError
from src.modules.document.ports import PageRaster

_PDF_MIME = "application/pdf"
_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/tiff"}

#: Point-to-inch ratio used by PDF page geometry.
_POINTS_PER_INCH = 72.0


class PypdfiumRasterizer:
    """PDF → per-page PNGs; images pass through as a single page."""

    def __init__(self, *, dpi: int) -> None:
        self._dpi = dpi

    def rasterize(self, data: bytes, mime_type: str) -> list[PageRaster]:
        if mime_type == _PDF_MIME:
            return self._rasterize_pdf(data)
        if mime_type in _IMAGE_MIMES:
            # Already a raster: pass through untouched as page 1. Width and
            # height are not needed until a box-producing engine maps
            # coordinates, so probing the image header is deferred.
            return [
                PageRaster(
                    page_no=1,
                    png_bytes=data,
                    width_px=0,
                    height_px=0,
                    dpi=self._dpi,
                )
            ]
        raise UnsupportedDocumentError(
            f"Unsupported mime type '{mime_type}' for automatic extraction."
        )

    def _rasterize_pdf(self, data: bytes) -> list[PageRaster]:
        try:
            document = pdfium.PdfDocument(data)
        except Exception as exc:
            raise UnsupportedDocumentError("The PDF could not be opened.") from exc
        try:
            scale = self._dpi / _POINTS_PER_INCH
            pages: list[PageRaster] = []
            for index in range(len(document)):
                page = document[index]
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                pages.append(
                    PageRaster(
                        page_no=index + 1,
                        png_bytes=buffer.getvalue(),
                        width_px=image.width,
                        height_px=image.height,
                        dpi=self._dpi,
                    )
                )
            return pages
        finally:
            document.close()
