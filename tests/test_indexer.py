"""Tests for README.md and offline index.html generation."""

from auto_knowledge_base.indexer import generate_index_html, generate_readme
from auto_knowledge_base.models import ArticleMetadata


def _save_sample(storage):
    meta = ArticleMetadata(url="https://example.com/a", title="Sample Article",
                           content_hash="h1", crawl_time="2026-06-11T00:00:00+00:00",
                           tags=["quantum", "qec"], category="Physics",
                           summary="A short LLM summary.")
    storage.save_article("# Sample Article\n\ncontent here", meta)
    return meta


class TestReadme:
    def test_contains_topic_keywords_and_articles(self, storage):
        _save_sample(storage)
        content = generate_readme(storage, topic="Quantum", keywords=["k1", "k2"])
        assert storage.readme_path.exists()
        assert "Quantum" in content
        assert "- k1" in content and "- k2" in content
        assert "Sample Article" in content
        assert "A short LLM summary." in content
        assert "Physics" in content

    def test_empty_kb_still_generates(self, storage):
        storage.init_layout()
        content = generate_readme(storage, topic="T", keywords=[])
        assert "Total articles: **0**" in content


class TestIndexHtml:
    def test_embeds_data_and_has_no_cdn(self, storage):
        _save_sample(storage)
        html = generate_index_html(storage)
        assert storage.index_html_path.exists()
        # Metadata and article body are embedded for file:// offline use.
        assert "Sample Article" in html
        assert "A short LLM summary." in html
        assert "content here" in html
        # Fully offline: no external script/style references allowed.
        assert "https://cdn" not in html
        assert 'src="http' not in html
        assert 'href="http' not in html.split("<script")[0]  # no external CSS in head

    def test_script_close_tag_is_escaped(self, storage):
        meta = ArticleMetadata(url="https://example.com/x", title="XSS-ish",
                               content_hash="h2", crawl_time="t", category="Misc",
                               summary="s")
        storage.save_article("hello </script><script>alert(1)</script>", meta)
        html = generate_index_html(storage)
        payload = html.split('id="kb-data"')[1].split("</script>")[0]
        # The embedded JSON must not contain an unescaped closing tag.
        assert "</script>" not in payload
