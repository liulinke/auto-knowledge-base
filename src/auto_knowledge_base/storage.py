"""Multi-user knowledge base storage.

Layout (one folder per user, one folder per knowledge base):

    <data_root>/<user_id>/<kb_name>/
        README.md, index.html
        Articles/<Category>/<slug>.md
        Attachments/
        Data/Raw/  Data/Processed/
        _Metadata/<Category>/<slug>.json   # mirrors Articles/ paths

The sidecar JSON files under `_Metadata/` are the single source of
truth for deduplication, so incremental runs need no extra state.
"""

import json
from pathlib import Path

from .models import ArticleMetadata
from .utils import slugify


class KnowledgeBaseStorage:
    """Filesystem operations for one (user, knowledge base) pair."""

    def __init__(self, data_root: Path | str, user_id: str, kb_name: str):
        # Slugify both identifiers so user input can never escape data_root.
        self.user_id = slugify(user_id)
        self.kb_name = slugify(kb_name)
        self.root = Path(data_root) / self.user_id / self.kb_name

    # --- well-known paths -------------------------------------------------

    @property
    def articles_dir(self) -> Path:
        return self.root / "Articles"

    @property
    def attachments_dir(self) -> Path:
        return self.root / "Attachments"

    @property
    def data_raw_dir(self) -> Path:
        return self.root / "Data" / "Raw"

    @property
    def data_processed_dir(self) -> Path:
        return self.root / "Data" / "Processed"

    @property
    def metadata_dir(self) -> Path:
        return self.root / "_Metadata"

    @property
    def readme_path(self) -> Path:
        return self.root / "README.md"

    @property
    def index_html_path(self) -> Path:
        return self.root / "index.html"

    # --- lifecycle ---------------------------------------------------------

    def init_layout(self) -> None:
        """Create the standard directory skeleton (idempotent)."""
        for d in (self.articles_dir, self.attachments_dir,
                  self.data_raw_dir, self.data_processed_dir,
                  self.metadata_dir):
            d.mkdir(parents=True, exist_ok=True)

    # --- metadata / dedup ----------------------------------------------------

    def list_metadata(self) -> list[ArticleMetadata]:
        """Load every sidecar JSON in the knowledge base."""
        if not self.metadata_dir.exists():
            return []
        out = []
        for p in sorted(self.metadata_dir.rglob("*.json")):
            try:
                out.append(ArticleMetadata.model_validate_json(p.read_text(encoding="utf-8")))
            except Exception:
                # A corrupt sidecar must not break the whole run; skip it.
                continue
        return out

    def known_urls(self) -> set[str]:
        return {m.url for m in self.list_metadata()}

    def known_hashes(self) -> set[str]:
        return {m.content_hash for m in self.list_metadata()}

    def is_duplicate_url(self, url: str) -> bool:
        return url in self.known_urls()

    def is_duplicate_hash(self, h: str) -> bool:
        return h in self.known_hashes()

    # --- writes ---------------------------------------------------------------

    def save_article(self, markdown: str, meta: ArticleMetadata) -> Path:
        """Write the article markdown plus its mirrored sidecar JSON.

        Returns the article path. A numeric suffix is appended on slug
        collision so distinct articles never overwrite each other.
        """
        self.init_layout()
        category = slugify(meta.category) or "General"
        slug = slugify(meta.title)

        article_dir = self.articles_dir / category
        article_dir.mkdir(parents=True, exist_ok=True)

        # Resolve slug collisions: foo.md, foo-2.md, foo-3.md ...
        candidate = slug
        n = 1
        while (article_dir / f"{candidate}.md").exists():
            n += 1
            candidate = f"{slug}-{n}"
        article_path = article_dir / f"{candidate}.md"

        meta.article_relpath = str(article_path.relative_to(self.root))
        article_path.write_text(markdown, encoding="utf-8")

        # Sidecar mirrors the article path: same category dir, same stem.
        sidecar_dir = self.metadata_dir / category
        sidecar_dir.mkdir(parents=True, exist_ok=True)
        sidecar_path = sidecar_dir / f"{candidate}.json"
        sidecar_path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")

        return article_path

    def read_article(self, relpath: str) -> str:
        """Read an article body by its kb-relative path."""
        return (self.root / relpath).read_text(encoding="utf-8")
