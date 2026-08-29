"""Vision adapter contract tests with a provider fake; no network or client data."""

from types import SimpleNamespace

from src.modules.document.infrastructure.vision_adapter import (
    LANGUAGE_HINTS,
    GoogleVisionOcrAdapter,
)
from src.modules.document.ports import PageRaster


def _box() -> SimpleNamespace:
    return SimpleNamespace(
        vertices=[
            SimpleNamespace(x=10, y=20),
            SimpleNamespace(x=50, y=20),
            SimpleNamespace(x=50, y=40),
            SimpleNamespace(x=10, y=40),
        ]
    )


def _property() -> SimpleNamespace:
    return SimpleNamespace(
        detected_languages=[SimpleNamespace(language_code="si", confidence=0.91)]
    )


class FakeVisionClient:
    def __init__(self) -> None:
        self.language_hints: list[str] = []

    def document_text_detection(self, *, image: object, image_context: object) -> object:
        _ = image
        self.language_hints = list(image_context.language_hints)
        symbols = [
            SimpleNamespace(
                text=value,
                confidence=0.9,
                property=_property(),
                bounding_box=_box(),
            )
            for value in "ගම"
        ]
        word = SimpleNamespace(
            symbols=symbols,
            confidence=0.88,
            property=_property(),
            bounding_box=_box(),
        )
        paragraph = SimpleNamespace(
            words=[word], confidence=0.87, property=_property(), bounding_box=_box()
        )
        block = SimpleNamespace(
            paragraphs=[paragraph], confidence=0.86, property=_property(), bounding_box=_box()
        )
        page = SimpleNamespace(
            width=100,
            height=200,
            property=_property(),
            blocks=[block],
        )
        annotation = SimpleNamespace(text="ගම", pages=[page])
        return SimpleNamespace(error=SimpleNamespace(message=""), full_text_annotation=annotation)


async def test_preserves_languages_confidence_and_ordered_normalized_polygons() -> None:
    client = FakeVisionClient()
    adapter = GoogleVisionOcrAdapter(client=client)  # type: ignore[arg-type]
    page = PageRaster(page_no=1, png_bytes=b"png", width_px=100, height_px=200, dpi=200)

    result = await adapter.document_text_detection(page)

    assert client.language_hints == list(LANGUAGE_HINTS) == ["si", "ta", "en"]
    assert result.text == "ගම"
    assert result.detected_languages[0].code == "si"
    word = result.words[0]
    assert word.confidence == 0.88
    assert [(point.x, point.y) for point in word.polygon] == [
        (0.1, 0.1),
        (0.5, 0.1),
        (0.5, 0.2),
        (0.1, 0.2),
    ]
