"""Split the law PDF into one chunk per article, with citation metadata."""
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PageObject, PdfReader

from mevzuat_rag.download import PDF_PATH, SOURCE_URL, download_law

LAW_NO = "4857"
LAW_NAME = "İş Kanunu"
CHUNKS_PATH = Path("data/processed/4857.jsonl")
EXPECTED_COUNTS = {"madde": 122, "ek": 3, "gecici": 12}

# The amendment tables after the last article repeat "Madde N" and must not be parsed.
LAW_END_MARKER = "4857 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN"

# A dash or "(" must follow the number: it separates real headings from wrapped
# cross-references. Article 87 has no dash: "Madde 87 (Mülga: ...)".
HEADING_RE = re.compile(
    r"^\s*(?:(?P<kind>Ek|Geçici)\s+)?Madde\s+(?P<no>\d+)\s*(?:[-–]|(?=\())\s*(?P<rest>.*)$"
)
SECTION_RE = re.compile(r"^\s*[A-ZÇĞİÖŞÜ]+ BÖLÜM\s*$")
# Body text is 12 pt, footnotes 11 pt and superscript note markers 8 pt or less.
# Filtering by size also drops footnotes that spill over onto the next page.
BODY_FONT_MIN_SIZE = 11.5
KIND_LABELS = {"madde": "Madde", "ek": "Ek Madde", "gecici": "Geçici Madde"}
KIND_KEYS = {None: "madde", "Ek": "ek", "Geçici": "gecici"}


@dataclass
class Chunk:
    id: str
    law_no: str
    article_type: str
    article_no: int
    title: str
    section: str
    citation: str
    is_repealed: bool
    text: str
    source_url: str


def extract_body_text(page: PageObject) -> str:
    """Keep only body-sized text; pypdf reports each text run with its font size."""
    parts: list[str] = []

    def keep_body_text(text, _cm, _tm, _font, font_size) -> None:
        if font_size >= BODY_FONT_MIN_SIZE:
            parts.append(text)

    page.extract_text(visitor_text=keep_body_text)
    return "".join(parts)


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_sections(lines: list[str]) -> dict[int, str]:
    """Record section starts by line index and blank them out of the body text."""
    sections: dict[int, str] = {}
    for index, line in enumerate(lines):
        if not SECTION_RE.match(line):
            continue
        name = collapse(line)
        lines[index] = ""
        following = index + 1
        while following < len(lines) and not lines[following].strip():
            following += 1
        if following < len(lines):
            name = f"{name}: {collapse(lines[following])}"
            lines[following] = ""
        sections[index] = name
    return sections


def find_title(lines: list[str], heading_index: int) -> tuple[int, str]:
    """An article title is the short unpunctuated text right above its heading."""
    # Removing a footnote block can leave a blank line under a page-bottom title.
    end = heading_index
    while end > 0 and not lines[end - 1].strip():
        end -= 1

    start = end
    while start > 0 and end - start < 2:
        candidate = lines[start - 1].strip()
        if not candidate or candidate.endswith((".", ":", ";", ",", ")")):
            break
        start -= 1
    return start, collapse(" ".join(lines[start:end]))


def build_chunks(lines: list[str], source_url: str = SOURCE_URL) -> list[Chunk]:
    lines = list(lines)
    sections = extract_sections(lines)
    headings = [(i, m) for i, line in enumerate(lines) if (m := HEADING_RE.match(line))]
    titles = [find_title(lines, i) for i, _ in headings]

    chunks = []
    for position, (index, match) in enumerate(headings):
        is_last = position + 1 == len(headings)
        end = len(lines) if is_last else titles[position + 1][0]
        kind = KIND_KEYS[match.group("kind")]
        number = int(match.group("no"))
        body = collapse(" ".join([match.group("rest"), *lines[index + 1 : end]]))
        section = next(
            (sections[i] for i in sorted(sections, reverse=True) if i < index),
            "",
        )
        label = f"{KIND_LABELS[kind]} {number}"
        prefix = "" if kind == "madde" else f"{kind}-"
        chunks.append(
            Chunk(
                id=f"{LAW_NO}-{prefix}{number}",
                law_no=LAW_NO,
                article_type=kind,
                article_no=number,
                title=titles[position][1],
                section=section,
                citation=f"{LAW_NO} sayılı {LAW_NAME}, {label}",
                is_repealed=bool(re.match(r"\(Mülga", body)),
                text=body,
                source_url=source_url,
            )
        )
    return chunks


def read_body_lines(pdf_path: Path) -> list[str]:
    pages = [extract_body_text(page) for page in PdfReader(pdf_path).pages]
    lines = "\n".join(pages).splitlines()
    for index, line in enumerate(lines):
        if LAW_END_MARKER in line:
            return lines[:index]
    raise ValueError("Law end marker not found; the PDF layout may have changed")


def validate(chunks: list[Chunk]) -> None:
    """Fail loudly: a silently lost article would become a wrong answer later."""
    for kind, expected in EXPECTED_COUNTS.items():
        numbers = [c.article_no for c in chunks if c.article_type == kind]
        if numbers != list(range(1, expected + 1)):
            raise ValueError(f"{kind}: expected 1..{expected}, got {numbers}")


def write_chunks(chunks: list[Chunk], target: Path = CHUNKS_PATH) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def main() -> None:
    download_law()
    chunks = build_chunks(read_body_lines(PDF_PATH))
    validate(chunks)
    write_chunks(chunks)
    print(f"{len(chunks)} chunks written to {CHUNKS_PATH}")


if __name__ == "__main__":
    main()
