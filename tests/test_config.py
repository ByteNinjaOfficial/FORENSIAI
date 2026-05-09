"""Tests for aiventra.core.config."""

import os
import pytest

from aiventra.core.config import Config


class TestConfig:
    def test_default_values(self):
        assert Config.API_BASE_URL == "https://api.featherless.ai/v1"
        assert Config.LLM_TEMPERATURE == 0.0
        assert Config.LLM_MAX_TOKENS == 4096
        assert Config.OCR_FALLBACK is True

    def test_validate_missing_key(self, monkeypatch):
        monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
        Config.API_KEY = ""
        with pytest.raises(EnvironmentError, match="FEATHERLESS_API_KEY"):
            Config.validate()

    def test_validate_with_key(self, monkeypatch):
        monkeypatch.setenv("FEATHERLESS_API_KEY", "test-key-123")
        Config.API_KEY = "test-key-123"
        Config.validate()

    def test_project_root_exists(self):
        assert Config.PROJECT_ROOT.exists()