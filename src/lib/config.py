"""
CivicLens shared configuration.

Loads environment variables and provides typed config access.
All ingestion clients and pipeline scripts import from here.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env.local for local dev; GitHub Actions uses repository secrets
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment."""

    # Supabase
    supabase_url: str = field(default_factory=lambda: os.environ["NEXT_PUBLIC_SUPABASE_URL"])
    supabase_service_key: str = field(
        default_factory=lambda: os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )

    # Data source APIs
    openstates_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENSTATES_API_KEY", "")
    )
    legiscan_api_key: str = field(default_factory=lambda: os.environ.get("LEGISCAN_API_KEY", ""))
    youtube_api_key: str = field(default_factory=lambda: os.environ.get("YOUTUBE_API_KEY", ""))

    # Model APIs
    google_ai_api_key: str = field(default_factory=lambda: os.environ.get("GOOGLE_AI_API_KEY", ""))

    # Application config
    model_routing_doc_threshold: int = field(
        default_factory=lambda: int(os.environ.get("MODEL_ROUTING_DOC_THRESHOLD", "3"))
    )
    rag_top_k: int = field(default_factory=lambda: int(os.environ.get("RAG_TOP_K", "8")))
    embedding_model: str = field(
        default_factory=lambda: os.environ.get("EMBEDDING_MODEL", "gemini")
    )

    # Jurisdiction constants for Bel Air MVP
    state_jurisdiction: str = "Maryland"
    county_jurisdiction: str = "Harford County"
    municipal_jurisdiction: str = "Town of Bel Air"


def get_config() -> Config:
    """Get application configuration. Raises on missing required vars."""
    # @spec INFRA-ENV-003
    try:
        return Config()
    except KeyError as exc:
        key = str(exc).strip("'\"")
        raise ValueError(f"Missing required environment variable: {key}") from exc
