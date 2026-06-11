"""Tests for the pure helper functions in auto_knowledge_base.utils."""

from auto_knowledge_base.utils import content_hash, extract_title, html_to_markdown, slugify


class TestSlugify:
    def test_basic_ascii(self):
        assert slugify("Hello World") == "Hello-World"

    def test_strips_unsafe_characters(self):
        assert slugify('a/b\\c:d*e?"<>|') == "a-b-cde"

    def test_keeps_cjk(self):
        # Chinese titles must stay readable in file names.
        assert slugify("量子计算 入门") == "量子计算-入门"

    def test_empty_falls_back(self):
        assert slugify("!!!") == "untitled"

    def test_length_capped(self):
        assert len(slugify("x" * 500)) <= 80


class TestContentHash:
    def test_stable(self):
        assert content_hash("abc") == content_hash("abc")

    def test_whitespace_insensitive(self):
        # Formatting-only differences must not defeat dedup.
        assert content_hash("a  b\n\nc") == content_hash("a b c")

    def test_different_content_differs(self):
        assert content_hash("abc") != content_hash("abd")


class TestHtmlToMarkdown:
    def test_converts_headings_and_strips_scripts(self):
        html = "<html><body><script>evil()</script><h1>Title</h1><p>Body</p></body></html>"
        md = html_to_markdown(html)
        assert "# Title" in md
        assert "evil" not in md

    def test_strips_nav_and_footer(self):
        html = "<body><nav>menu</nav><p>real content</p><footer>foot</footer></body>"
        md = html_to_markdown(html)
        assert "real content" in md
        assert "menu" not in md and "foot" not in md


class TestExtractTitle:
    def test_from_title_tag(self):
        assert extract_title("<html><head><title> My Page </title></head></html>") == "My Page"

    def test_from_h1_when_no_title(self):
        assert extract_title("<body><h1>H1 Title</h1></body>") == "H1 Title"

    def test_fallback(self):
        assert extract_title("<body></body>", fallback="fb") == "fb"
