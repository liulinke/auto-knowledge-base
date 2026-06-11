"""Pure helper functions: slugs, hashing, time, HTML fetching/conversion."""

import hashlib
import re
import unicodedata
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify


def slugify(text: str, max_len: int = 80) -> str:
    """Turn arbitrary text into a filesystem-safe slug.

    Keeps CJK characters (they are valid in file names and preserve
    readability for Chinese titles); replaces everything else unsafe
    with hyphens.
    """
    text = unicodedata.normalize("NFKC", text).strip()
    # Replace path separators and whitespace runs with a hyphen.
    text = re.sub(r"[\s/\\]+", "-", text)
    # Drop characters that are risky in file names across platforms.
    text = re.sub(r"[^\w\-一-鿿]", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:max_len] or "untitled"


def content_hash(text: str) -> str:
    """MD5 of the normalized text body, used for content-level dedup.

    Whitespace is collapsed so that trivial formatting differences do
    not defeat deduplication.
    """
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string (stored in metadata)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def html_to_markdown(html: str) -> str:
    """Convert an HTML page to clean Markdown.

    Scripts, styles and navigation chrome are stripped first so the
    markdown only contains the article body text.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    md = markdownify(str(soup), heading_style="ATX")
    # Collapse runs of 3+ blank lines that markdownify tends to leave.
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def extract_title(html: str, fallback: str = "Untitled") -> str:
    """Best-effort page title extraction from <title> or first <h1>."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return fallback


def fetch_url(url: str, timeout: float = 20.0) -> str | None:
    """Download a page and return its HTML, or None on any failure.

    Failures are swallowed on purpose: a single dead link must never
    abort a whole collection run.
    """
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"User-Agent": "auto-knowledge-base/0.1"})
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None
