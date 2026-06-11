"""Tests for .env loading and environment-driven configuration."""

import os

from auto_knowledge_base.config import AppConfig, DEFAULT_MODEL, load_env


class TestAppConfig:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("AUTO_KB_DATA_ROOT", raising=False)
        monkeypatch.delenv("AUTO_KB_MODEL", raising=False)
        cfg = AppConfig()
        assert str(cfg.data_root) == "kb_data"
        assert cfg.model_name == DEFAULT_MODEL == "gpt-4o-mini"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("AUTO_KB_DATA_ROOT", "/tmp/kbs")
        monkeypatch.setenv("AUTO_KB_MODEL", "gpt-4o")
        cfg = AppConfig()
        assert str(cfg.data_root) == "/tmp/kbs"
        assert cfg.model_name == "gpt-4o"


class TestLoadEnv:
    def test_reads_dotenv_file(self, tmp_path, monkeypatch):
        # Keys defined in .env must land in os.environ.
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        (tmp_path / ".env").write_text(
            "OPENAI_API_KEY=sk-test-123\nTAVILY_API_KEY=tvly-test\n",
            encoding="utf-8")
        load_env()
        assert os.environ["OPENAI_API_KEY"] == "sk-test-123"
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    def test_real_env_wins_over_dotenv(self, tmp_path, monkeypatch):
        # Deployment overrides must not be clobbered by the .env file.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-from-file\n",
                                       encoding="utf-8")
        load_env()
        assert os.environ["OPENAI_API_KEY"] == "sk-from-env"
