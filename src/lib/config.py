"""
CivicLens shared configuration.

Loads environment variables and provides typed config access.
All ingestion clients and pipeline scripts import from here.

Locality configuration is loaded from civic-lens.config.json at project root.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Project root: two levels up from src/lib/config.py
_PROJECT_ROOT = Path(__file__).parent.parent.parent

# Load .env.local for local dev; GitHub Actions uses repository secrets
load_dotenv(_PROJECT_ROOT / ".env.local")

# ─── Locality Config (from civic-lens.config.json) ────────────────────

_locality_config: dict[str, Any] | None = None


def _load_locality() -> dict[str, Any]:
    """Load and cache the locality config from civic-lens.config.json."""
    global _locality_config
    if _locality_config is None:
        config_path = _PROJECT_ROOT / "civic-lens.config.json"
        with open(config_path) as f:
            _locality_config = json.load(f)
    return _locality_config


def get_locality() -> dict[str, Any]:
    """Get the full locality configuration."""
    return _load_locality()


def get_state_config() -> dict[str, Any]:
    """Get state-level configuration."""
    return _load_locality()["locality"]["state"]


def get_county_config() -> dict[str, Any] | None:
    """Get county-level configuration, or None if not configured."""
    return _load_locality()["locality"].get("county")


def get_municipal_config() -> dict[str, Any] | None:
    """Get municipal-level configuration, or None if not configured."""
    return _load_locality()["locality"].get("municipal")


def get_display_config() -> dict[str, Any]:
    """Get display/UI configuration."""
    return _load_locality()["display"]


def get_scraper_config(jurisdiction: str, scraper_name: str) -> dict[str, Any] | None:
    """Get a scraper's config from a jurisdiction section, or None if not configured."""
    cfg = get_county_config() if jurisdiction == "county" else get_municipal_config()
    if cfg and scraper_name in cfg.get("scrapers", {}):
        return cfg["scrapers"][scraper_name]
    return None


# ─── Environment Config ───────────────────────────────────────────────

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

    # Jurisdiction constants — loaded from civic-lens.config.json
    state_jurisdiction: str = field(default_factory=lambda: get_state_config()["name"])
    county_jurisdiction: str = field(
        default_factory=lambda: c["name"] if (c := get_county_config()) else ""
    )
    municipal_jurisdiction: str = field(
        default_factory=lambda: m["name"] if (m := get_municipal_config()) else ""
    )


def get_config() -> Config:
    """Get application configuration. Raises on missing required vars."""
    # @spec INFRA-ENV-003
    try:
        return Config()
    except KeyError as exc:
        key = str(exc).strip("'\"")
        raise ValueError(f"Missing required environment variable: {key}") from exc
