"""Tests for multi-user storage, sidecar metadata and deduplication."""

import json

from auto_kb.models import ArticleMetadata
from auto_kb.storage import KnowledgeBaseStorage


def _meta(url="https://example.com/x", title="My Article",
          category="AI", h="hash123") -> ArticleMetadata:
    return ArticleMetadata(url=url, title=title, content_hash=h,
                           crawl_time="2026-06-11T00:00:00+00:00",
                           tags=["t1"], category=category, summary="a summary")


class TestLayout:
    def test_init_creates_standard_skeleton(self, storage):
        storage.init_layout()
        assert storage.articles_dir.is_dir()
        assert storage.attachments_dir.is_dir()
        assert storage.data_raw_dir.is_dir()
        assert storage.data_processed_dir.is_dir()
        assert storage.metadata_dir.is_dir()

    def test_init_is_idempotent(self, storage):
        storage.init_layout()
        storage.init_layout()  # must not raise

    def test_multi_user_isolation(self, tmp_path):
        a = KnowledgeBaseStorage(tmp_path, "alice", "kb1")
        b = KnowledgeBaseStorage(tmp_path, "bob", "kb1")
        assert a.root != b.root
        assert a.root.parent.name == "alice"
        assert b.root.parent.name == "bob"

    def test_path_traversal_is_neutralized(self, tmp_path):
        s = KnowledgeBaseStorage(tmp_path, "../evil", "../../kb")
        # The slugified path must stay inside data_root.
        assert tmp_path in s.root.parents


class TestSaveArticle:
    def test_writes_article_and_mirrored_sidecar(self, storage):
        path = storage.save_article("# body", _meta())
        assert path.exists()
        assert path.suffix == ".md"
        # Sidecar mirrors Articles/<cat>/<slug>.md as _Metadata/<cat>/<slug>.json
        sidecar = storage.metadata_dir / "AI" / (path.stem + ".json")
        assert sidecar.exists()
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert data["url"] == "https://example.com/x"
        assert data["summary"] == "a summary"
        assert data["article_relpath"] == "Articles/AI/" + path.name

    def test_slug_collision_gets_suffix(self, storage):
        p1 = storage.save_article("body one", _meta(h="h1"))
        p2 = storage.save_article("body two", _meta(url="https://example.com/y", h="h2"))
        assert p1 != p2
        assert p1.read_text(encoding="utf-8") == "body one"
        assert p2.read_text(encoding="utf-8") == "body two"


class TestDedup:
    def test_url_dedup(self, storage):
        storage.save_article("body", _meta())
        assert storage.is_duplicate_url("https://example.com/x")
        assert not storage.is_duplicate_url("https://example.com/other")

    def test_hash_dedup(self, storage):
        storage.save_article("body", _meta())
        assert storage.is_duplicate_hash("hash123")
        assert not storage.is_duplicate_hash("otherhash")

    def test_list_metadata_skips_corrupt_files(self, storage):
        storage.save_article("body", _meta())
        bad = storage.metadata_dir / "broken.json"
        bad.write_text("{not valid json", encoding="utf-8")
        metas = storage.list_metadata()
        assert len(metas) == 1  # corrupt sidecar ignored, run not aborted

    def test_empty_kb_has_no_known_urls(self, storage):
        assert storage.known_urls() == set()
        assert storage.known_hashes() == set()
