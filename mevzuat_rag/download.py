"""Download the official consolidated text of Labour Law No. 4857."""
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "https://www.mevzuat.gov.tr/MevzuatMetin/1.5.4857.pdf"
PDF_PATH = Path("data/raw/4857.pdf")
USER_AGENT = "mevzuat-rag/0.1"


def download_law(url: str = SOURCE_URL, target: Path = PDF_PATH) -> Path:
    """Fetch the PDF once; an existing copy is reused so the corpus stays stable."""
    if target.exists():
        return target

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
    print(f"PDF ready: {download_law()}")
