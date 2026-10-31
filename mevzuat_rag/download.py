"""Download the official consolidated law texts."""
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URLS = {
    "4857": "https://www.mevzuat.gov.tr/MevzuatMetin/1.5.4857.pdf",
    "1475": "https://www.mevzuat.gov.tr/MevzuatMetin/1.5.1475.pdf",
}
RAW_DIR = Path("data/raw")
USER_AGENT = "mevzuat-rag/0.1"


def pdf_path(law_no: str) -> Path:
    return RAW_DIR / f"{law_no}.pdf"


def download_law(law_no: str) -> Path:
    """Fetch a PDF once; an existing copy is reused so the corpus stays stable."""
    target = pdf_path(law_no)
    if target.exists():
        return target

    url = SOURCE_URLS[law_no]
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read()

    # The site can answer HTTP 200 with an HTML error page, so check the bytes.
    if not content.startswith(b"%PDF"):
        raise ValueError(f"Expected a PDF from {url}, got something else")

    # Write to a temp file first so a failed write never leaves a partial PDF.
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
        tmp.write(content)
    Path(tmp.name).replace(target)
    return target


if __name__ == "__main__":
    for law_no in SOURCE_URLS:
        print(f"PDF ready: {download_law(law_no)}")
