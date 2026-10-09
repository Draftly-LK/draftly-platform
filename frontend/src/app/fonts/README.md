# Bundled application fonts

These are the existing four application font families, stored locally so builds
do not depend on Google Fonts CSS or font downloads. The WOFF2 files contain the
full upright variable fonts. No glyphs were subsetted, axes instantiated, names
changed, or outlines edited.

All originals and their accompanying licenses came from the official
[Google Fonts repository at commit `34596296b4e88c29e40df100d488055ac17dbd56`](https://github.com/google/fonts/tree/34596296b4e88c29e40df100d488055ac17dbd56).
The four original TTFs total 3,955,636 bytes; the four bundled WOFF2 files total
1,228,828 bytes. Original TTF copies used for verification are kept only in the
ignored `.local-ci/font-originals` directory, not shipped with the application.

## Sources and licenses

All four fonts use the SIL Open Font License, Version 1.1. The files linked below
are unmodified copies of each upstream `OFL.txt`, including its copyright notice.

| Local WOFF2 file | Original source at the pinned revision | License and copyright holder |
| --- | --- | --- |
| `ibm-plex-sans.woff2` | [IBMPlexSans\[wdth,wght\].ttf](https://raw.githubusercontent.com/google/fonts/34596296b4e88c29e40df100d488055ac17dbd56/ofl/ibmplexsans/IBMPlexSans%5Bwdth%2Cwght%5D.ttf) | [ibm-plex-sans.OFL.txt](ibm-plex-sans.OFL.txt): 2017 IBM Corp.; reserved font name "Plex" |
| `noto-sans-sinhala.woff2` | [NotoSansSinhala\[wdth,wght\].ttf](https://raw.githubusercontent.com/google/fonts/34596296b4e88c29e40df100d488055ac17dbd56/ofl/notosanssinhala/NotoSansSinhala%5Bwdth%2Cwght%5D.ttf) | [noto-sans-sinhala.OFL.txt](noto-sans-sinhala.OFL.txt): 2022 The Noto Project Authors |
| `source-serif-4.woff2` | [SourceSerif4\[opsz,wght\].ttf](https://raw.githubusercontent.com/google/fonts/34596296b4e88c29e40df100d488055ac17dbd56/ofl/sourceserif4/SourceSerif4%5Bopsz%2Cwght%5D.ttf) | [source-serif-4.OFL.txt](source-serif-4.OFL.txt): 2014 The Source Serif 4 Project Authors |
| `noto-serif-sinhala.woff2` | [NotoSerifSinhala\[wdth,wght\].ttf](https://raw.githubusercontent.com/google/fonts/34596296b4e88c29e40df100d488055ac17dbd56/ofl/notoserifsinhala/NotoSerifSinhala%5Bwdth%2Cwght%5D.ttf) | [noto-serif-sinhala.OFL.txt](noto-serif-sinhala.OFL.txt): 2022 The Noto Project Authors |

## File checksums

Hashes are SHA-256; sizes are bytes.

| Family | Original TTF size | Original TTF SHA-256 | WOFF2 size | WOFF2 SHA-256 |
| --- | ---: | --- | ---: | --- |
| IBM Plex Sans | 537244 | `3b031aa4216174205bd8471f88a49b91f093169e9e87bd5262242bc5967fe2e3` | 236616 | `e291b60bbb1859d657bb5ce619ac7bb72f66b65eaad569ca1248ce668f04361c` |
| Noto Sans Sinhala | 1181956 | `9bd93e407a278075be403324063bc94a7e306c44de4df81214e932330c22eecf` | 303784 | `15c6da22e41b38a8631167146afaa7395a08b6f74d21a22c0d8f20f3b2875d9f` |
| Source Serif 4 | 1209508 | `97b2d4da6e3cb494b5a1e66ae176914d852ccabef49e0c02c0df25f3e39aca0b` | 436484 | `11003b7885b648b7e5440d1ec8b0d3b2245a53fd5c8ab53adfa86a0175b315e7` |
| Noto Serif Sinhala | 1026928 | `2b0df6b8bde56d3b934ba89fada82486b1ec50ee06842c81be36496f8c9b5ac9` | 251944 | `d5760d9238fe0c3783a56972890f3d891e88172a029fc527aa122c9ce80250d7` |

| License file | Size | SHA-256 |
| --- | ---: | --- |
| `ibm-plex-sans.OFL.txt` | 4456 | `7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da` |
| `noto-sans-sinhala.OFL.txt` | 4383 | `2d6f7c43bce61f4b1919379f901bc613484f5285f520b6d29bb7c1f31b17e841` |
| `source-serif-4.OFL.txt` | 4400 | `5f94c3fd3a23131a417ab5a0c8452de57e70c3cfb9f604d88241f7065ebf9fd9` |
| `noto-serif-sinhala.OFL.txt` | 4383 | `2d6f7c43bce61f4b1919379f901bc613484f5285f520b6d29bb7c1f31b17e841` |

## Compression and table verification

Conversion used Python 3.12, fontTools 4.66.1 and Brotli 1.2.0 in a temporary
`uv run --no-project --with fonttools==4.66.1 --with brotli==1.2.0` environment.
These are not project or runtime dependencies. Each renamed original TTF was
converted with:

```python
from fontTools.ttLib import TTFont
from fontTools.ttLib.woff2 import WOFF2FlavorData

font = TTFont(source, lazy=True, recalcBBoxes=False, recalcTimestamp=False)
font.flavor = "woff2"
font.flavorData = WOFF2FlavorData(transformedTables=set())
font.save(target)
font.close()
```

All optional WOFF2 table transformations are disabled. The WOFF2 metadata and
private-data blocks are absent. Original `name`, `fvar`, `GSUB`, `GPOS`, `glyf`,
`loca`, and every other surviving table were compared byte-for-byte against the
decompressed WOFF2 tables, with these format-required exceptions:

- `head.flags` bit 11 is set, as required by the
  [WOFF2 specification, section 5](https://www.w3.org/TR/WOFF2/).
- `head.checkSumAdjustment` is recalculated for the reconstructed font. All
  other `head` bytes, including timestamps and bounds, are identical.
- Source Serif 4's empty `DSIG` placeholder (`0000000100000000`, zero signatures)
  is removed. WOFF2 section 5 requires removal of this table because conversion
  invalidates original binary signatures. The other three fonts have no `DSIG`.

This follows the unchanged-font-data compression approach described in the
[OFL FAQ, section 2.2.1](https://openfontlicense.org/ofl-faq/).
The internal family names, copyright, license fields, glyph order, character
maps, variation axes, metrics, outlines, and shaping tables are preserved.

| Family | Original/WOFF2 table count | Glyph count | Best character-map entries | Original/WOFF2 `head.flags` | Original/WOFF2 checksum adjustment |
| --- | --- | ---: | ---: | --- | --- |
| IBM Plex Sans | 24/24 | 1025 | 891 | 10/2058 | `a74e6493` / `970b44c3` |
| Noto Sans Sinhala | 20/20 | 979 | 453 | 3/2051 | `c9daaf5f` / `b96d9133` |
| Source Serif 4 | 22/21 | 1463 | 918 | 3/2051 | `dd88d48b` / `115720bc` |
| Noto Serif Sinhala | 20/20 | 976 | 451 | 3/2051 | `e08a1c79` / `d02f4735` |

## Verified family and language coverage

Next.js 15.5.21's bundled fontkit parsed all four TTF and WOFF2 files. Its reported
family names and variable axes are:

| Family | Font version | Weight axis (default) | Other axis (default) | Application weight range |
| --- | --- | --- | --- | --- |
| IBM Plex Sans | 3.201 | 100–700 (400) | width 75–100 (100) | 400–600 |
| Noto Sans Sinhala | 2.006 | 100–900 (400) | width 62.5–100 (100) | 100–900 |
| Source Serif 4 | 4.004 | 200–900 (400) | optical size 8–60 (20) | 500–700 |
| Noto Serif Sinhala | 2.007 | 100–900 (400) | width 62.5–100 (100) | 500–700 |

All four files contain the 62 ASCII Latin letters and digits. Both Noto Sinhala
files contain all 58 distinct Sinhala-block code points present in the current
`si.json` message catalogue. Fontkit shaped the sample `සිංහල ශ්‍රී ලංකා` with
zero missing glyphs in each Sinhala font. IBM Plex Sans and Source Serif 4 do
not contain those Sinhala code points, so the paired Sinhala families remain
necessary. These checks establish font-data coverage; they are not a substitute
for the separate browser layout and native-language review gates.
