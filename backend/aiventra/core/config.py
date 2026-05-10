"""Application configuration loaded from environment variables and .env file."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Config:
    API_KEY: str = os.getenv("FEATHERLESS_API_KEY", "")
    API_BASE_URL: str = os.getenv(
        "FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"
    )
    MODEL_NAME: str = os.getenv(
        "AIVENTRA_MODEL", "deepseek-ai/DeepSeek-V4-Pro"
    )
    LLM_TEMPERATURE: float = float(os.getenv("AIVENTRA_LLM_TEMPERATURE", "0.0"))
    LLM_MAX_TOKENS: int = int(os.getenv("AIVENTRA_LLM_MAX_TOKENS", "4096"))
    OCR_FALLBACK: bool = os.getenv("AIVENTRA_OCR_FALLBACK", "true").lower() == "true"
    TESSERACT_CMD: Optional[str] = os.getenv("TESSERACT_CMD")
    PROJECT_ROOT: Path = _PROJECT_ROOT

    @classmethod
    def validate(cls) -> None:
        missing = []
        if not cls.API_KEY:
            missing.append("FEATHERLESS_API_KEY")
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Set them in .env or export them before running."
            )

    @classmethod
    def reload(cls) -> None:
        load_dotenv(override=True)
        cls.API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
        cls.API_BASE_URL = os.getenv(
            "FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"
        )
        cls.MODEL_NAME = os.getenv(
            "AIVENTRA_MODEL", "deepseek-ai/DeepSeek-V4-Pro"
        )
        cls.LLM_TEMPERATURE = float(os.getenv("AIVENTRA_LLM_TEMPERATURE", "0.0"))
        cls.LLM_MAX_TOKENS = int(os.getenv("AIVENTRA_LLM_MAX_TOKENS", "4096"))
        cls.OCR_FALLBACK = os.getenv("AIVENTRA_OCR_FALLBACK", "true").lower() == "true"
        cls.TESSERACT_CMD = os.getenv("TESSERACT_CMD")