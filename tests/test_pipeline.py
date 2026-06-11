"""End-to-end pipeline tests with a fake LLM and fake search client."""

from langchain_core.language_models import FakeListChatModel

from auto_knowledge_base.pipeline import build_pipeline, parse_article_analysis

from .conftest import FakeSearchClient

ANALYSIS_A = "SUMMARY: QEC protects qubits.\nCATEGORY: Error Correction\nTAGS: qec, noise"
ANALYSIS_B = "SUMMARY: Surface codes lead fault tolerance.\nCATEGORY: Surface Codes\nTAGS: codes"


def _llm(extra_analyses: list[str]):
    """Fake LLM replaying: optimize -> keywords -> one analysis per article."""
    return FakeListChatModel(responses=[
        "Refined quantum error correction research topic",
        "quantum error correction\nsurface codes",
        *extra_analyses,
    ])


class TestParseArticleAnalysis:
    def test_parses_all_fields(self):
        s, c, t = parse_article_analysis(ANALYSIS_A, body="ignored")
        assert s == "QEC protects qubits."
        assert c == "Error Correction"
        assert t == ["qec", "noise"]

    def test_malformed_reply_falls_back(self):
        s, c, t = parse_article_analysis("totally unstructured", body="body text here")
        assert s.startswith("body text")
        assert c == "General"
        assert t == []


class TestPipeline:
    def test_full_run_saves_articles_with_llm_summary(self, storage, fake_results):
        llm = _llm([ANALYSIS_A, ANALYSIS_B])
        pipeline = build_pipeline(llm, FakeSearchClient(fake_results), storage)
        result = pipeline.invoke({"topic": "quantum"})

        assert result["optimized_topic"] == "Refined quantum error correction research topic"
        assert result["keywords"] == ["quantum error correction", "surface codes"]
        assert len(result["saved"]) == 2

        # Every saved article carries an LLM-generated summary in its sidecar.
        metas = {m.url: m for m in storage.list_metadata()}
        assert metas["https://example.com/a"].summary == "QEC protects qubits."
        assert metas["https://example.com/a"].category == "Error Correction"
        assert metas["https://example.com/b"].tags == ["codes"]

        # Index entry points are rebuilt at the end of the run.
        assert storage.readme_path.exists()
        assert storage.index_html_path.exists()

    def test_second_run_skips_duplicates(self, storage, fake_results):
        # First run fills the kb.
        pipeline1 = build_pipeline(_llm([ANALYSIS_A, ANALYSIS_B]),
                                   FakeSearchClient(fake_results), storage)
        pipeline1.invoke({"topic": "quantum"})

        # Second incremental run sees the same URLs and must skip them all.
        pipeline2 = build_pipeline(_llm([]),  # no analysis calls expected
                                   FakeSearchClient(fake_results), storage)
        result = pipeline2.invoke({"topic": "quantum"})
        assert result["saved"] == []
        assert result["skipped"] == 2
        assert len(storage.list_metadata()) == 2  # nothing duplicated on disk

    def test_results_without_content_are_skipped_not_fatal(self, storage, fake_results):
        # Empty body must be skipped without aborting the run.
        fake_results[0].raw_content = "   "
        fake_results[1].raw_content = "Real content " * 10
        pipeline = build_pipeline(_llm([ANALYSIS_B]),
                                  FakeSearchClient(fake_results), storage)
        result = pipeline.invoke({"topic": "quantum"})
        assert len(result["saved"]) == 1
        assert result["skipped"] == 1
