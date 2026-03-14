#!/usr/bin/env python3
"""
Run the full CivicLens ingestion pipeline locally.

Usage:
    python scripts/run_pipeline.py [--source SOURCE] [--skip-embed]

Sources: openstates, legiscan, ecode360, belair, all (default)
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("civiclens.pipeline")


def main():
    parser = argparse.ArgumentParser(description="Run CivicLens ingestion pipeline")
    parser.add_argument(
        "--source",
        choices=["openstates", "legiscan", "ecode360", "belair", "all"],
        default="all",
        help="Which data source to ingest (default: all)",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Skip embedding generation after ingestion",
    )
    args = parser.parse_args()

    # Step 1: Ingestion
    if args.source in ("openstates", "all"):
        logger.info("═══ Ingesting: Open States (MD state bills) ═══")
        from src.ingestion.clients.openstates import ingest_state_bills
        ingest_state_bills()

    if args.source in ("legiscan", "all"):
        logger.info("═══ Ingesting: LegiScan (MD state bills) ═══")
        from src.ingestion.clients.legiscan import ingest_legiscan_bills
        ingest_legiscan_bills()

    if args.source in ("ecode360", "all"):
        logger.info("═══ Ingesting: eCode360 (Bel Air town code) ═══")
        from src.ingestion.scrapers.ecode360 import ingest_municipal_code
        ingest_municipal_code()

    if args.source in ("belair", "all"):
        logger.info("═══ Ingesting: Bel Air legislation page ═══")
        from src.ingestion.scrapers.belair_legislation import ingest_belair_legislation
        ingest_belair_legislation()

    # Step 2: Normalization
    logger.info("═══ Running Bronze → Silver normalization ═══")
    from src.pipeline.normalize import run_normalization
    run_normalization()

    # Step 3: Embedding (optional)
    if not args.skip_embed:
        logger.info("═══ Running embedding pipeline ═══")
        from src.pipeline.embedder import run_embedding_pipeline
        run_embedding_pipeline()
    else:
        logger.info("Skipping embedding generation (--skip-embed)")

    logger.info("═══ Pipeline complete ═══")


if __name__ == "__main__":
    main()
