"""Transcribe one prescribed form from Gazette Extraordinary 1886/58 to Unicode.

The gazette PDF carries its Sinhala text in the legacy FM Abhaya font encoding
(ASCII code points drawn as Sinhala glyphs), so a plain text extraction reads
as Latin noise. This script maps FM Abhaya to Unicode Sinhala, reorders the
pre-base vowel signs, and writes the form's lines verbatim. Nothing is
corrected: spelling variants printed in the gazette are kept as printed.

Usage (from the repository root):

    uv run --with pymupdf python docs/reference/tools/fm_abhaya_to_unicode.py \
        docs/reference/1886-58_S.pdf 08 > docs/reference/forms/transcriptions/si/form-08.txt

Every transcription must still be proof-read against the page image before a
template relies on it; unmapped glyphs are reported on stderr.
"""

from __future__ import annotations

import re
import sys

import pymupdf

# Multi-character keys are matched before single characters.
_PAIRS: list[tuple[str, str]] = [
    ("wd", "ආ"), ("we", "ඇ"), ("wE", "ඈ"), ("ta", "ඒ"), ("W!", "ඌ"), ("T!", "ඖ"),
    ("re", "රු"), ("rE", "රූ"), ("DD", "ෲ"),
    ("w", "අ"), ("b", "ඉ"), ("B", "ඊ"), ("W", "උ"), ("t", "එ"), ("T", "ඔ"), ("´", "ඕ"),
    ("l", "ක"), ("L", "ඛ"), (".", "ග"), (">", "ඝ"), ("x", "ං"), ("X", "ඞ"), ("Õ", "ඟ"),
    ("p", "ච"), ("P", "ඡ"), ("c", "ජ"), ("[", "ඤ"), ("{", "ඥ"), ("g", "ට"), ("G", "ඨ"),
    ("v", "ඩ"), ("V", "ඪ"), ("K", "ණ"), ("~", "ඬ"), (";", "ත"), (":", "ථ"), ("o", "ද"),
    ("O", "ධ"), ("k", "න"), ("|", "ඳ"), ("m", "ප"), ("M", "ඵ"), ("n", "බ"), ("N", "භ"),
    ("u", "ම"), ("U", "ඹ"), ("h", "ය"), ("r", "ර"), (",", "ල"), ("j", "ව"), ("Y", "ශ"),
    ("I", "ෂ"), ("i", "ස"), ("y", "හ"), ("<", "ළ"), ("*", "ෆ"),
    ("ñ", "මි"), ("È", "දි"), ("Ñ", "චි"), ("Í", "රී"), ("ß", "රි"), ("ú", "වි"),
    ("ù", "වී"), ("ÿ", "දු"), ("÷", "ඳු"), ("ø", "ද්‍ර"), ("ï", "ම්"), ("õ", "ව්"),
    ("Ü", "ට්"), ("§", "දී"), ("¿", "ළු"), ("ê", "ධි"), ("Ô", "ජී"), ("ð", "ජි"),
    ("ì", "බි"), ("£", "ඳී"), ("¢", "ඳි"), ("á", "ටි"),
    ("d", "ා"), ("e", "ැ"), ("E", "ෑ"), ("s", "ි"), ("S", "ී"), ("q", "ු"), ("Q", "ූ"),
    ("=", "ු"), ("+", "ූ"), ("D", "ෘ"), ("a", "්"), ("H", "්‍ය"), ("%", "්‍ර"),
    ("¾", "ර්"), ("!", "ෟ"),
    ("'", "."), ("(", ":"), ("^", "("), ("&", ")"), ('"', ","), ("˜", "”"), ("z", "‘"),
    ("$", "/"),
]
_PAIRS.sort(key=lambda pair: -len(pair[0]))

_E_SIGN = ""
_AI_SIGN = ""
_CONSONANTS = "කඛගඝඞඟචඡජඣඤඥටඨඩඪණඬතථදධනඳපඵබභමඹයරලවශෂසහළෆ"
_PRE_BASE = re.compile(f"([{_E_SIGN}{_AI_SIGN}])([{_CONSONANTS}])((?:්‍[රය])?)")


def convert(text: str, unknown: dict[str, int] | None = None) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("ff", i):
            out.append(_AI_SIGN)
            i += 2
            continue
        if text[i] == "f":
            out.append(_E_SIGN)
            i += 1
            continue
        for key, value in _PAIRS:
            if text.startswith(key, i):
                out.append(value)
                i += len(key)
                break
        else:
            char = text[i]
            if unknown is not None and ord(char) > 127:
                unknown[char] = unknown.get(char, 0) + 1
            out.append(char)
            i += 1
    result = "".join(out)
    result = _PRE_BASE.sub(
        lambda m: m.group(2) + m.group(3) + ("ෙ" if m.group(1) == _E_SIGN else "ෛ"), result
    )
    return (
        result.replace("ේ", "ේ")
        .replace("ො", "ො")
        .replace("ෝ", "ෝ")
        .replace("ෞ", "ෞ")
    )


# Where each form starts, and the page after its attestation block ends.
_FORMS = {"08": (4, 6), "12": (13, 14)}
_RUNNING_HEADER = re.compile(r"(ගැසට් පත්‍රය - 2014\.10\.31|^\s*\d+\s+A\s*$)")


def transcribe(pdf_path: str, form: str) -> tuple[list[str], dict[str, int]]:
    first, last = _FORMS[form]
    document = pymupdf.open(pdf_path)
    unknown: dict[str, int] = {}
    lines: list[str] = []
    for page in range(first, last + 1):
        for line in convert(document[page - 1].get_text(), unknown).split("\n"):
            if _RUNNING_HEADER.search(line) or not line.strip():
                continue
            lines.append(line.strip())
    start = next(i for i, line in enumerate(lines) if line == f"ආකෘති පත්‍ර අංක - {form}")
    end = next(i for i in range(start, len(lines)) if lines[i] == "අත්සන හා නිල මුද්‍රාව.")
    return lines[start : end + 1], unknown


def main() -> None:
    pdf_path, form = sys.argv[1], sys.argv[2]
    lines, unknown = transcribe(pdf_path, form)
    print("\n".join(lines))
    if unknown:
        print(f"unmapped glyphs: {unknown}", file=sys.stderr)


if __name__ == "__main__":
    main()
