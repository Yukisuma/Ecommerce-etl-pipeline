"""
src/pipeline.py — Main ETL Orchestrator
Usage:
    python src/pipeline.py              # Full run
    python src/pipeline.py --no-report  # Skip report generation
    python src/pipeline.py --dry-run    # Validate only (no DB writes)
"""

import sys
import logging
import argparse
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src.extract import Extractor
from src.transform import Transformer
from src.load import Loader
from src.report import ReportGenerator

# ─── Logging Setup ────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> logging.Logger:
    log_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s  %(levelname)-8s  %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt,
                        handlers=[
                            logging.StreamHandler(sys.stdout),
                            logging.FileHandler(config.LOG_FILE, mode="a"),
                        ])
    return logging.getLogger("pipeline")


# ─── Banner ───────────────────────────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════╗
║     🛍️   E-COMMERCE DATA PIPELINE   v1.0               ║
║          Extract · Transform · Load · Report            ║
╚══════════════════════════════════════════════════════════╝
"""


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def run_pipeline(dry_run: bool = False, skip_report: bool = False):
    logger = setup_logging(config.LOG_LEVEL)
    print(BANNER)

    start_time = time.time()
    logger.info(f"🚀 Pipeline started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"   Mode: {'DRY RUN (no DB writes)' if dry_run else 'PRODUCTION'}")
    logger.info(f"   Report: {'SKIP' if skip_report else 'ENABLED'}")
    logger.info("")

    try:
        # ── 1. EXTRACT ──────────────────────────────────────────────────────
        extractor = Extractor(
            raw_dir=config.RAW_DATA_DIR,
            expected_columns=config.EXPECTED_COLUMNS,
        )
        datasets = extractor.extract_all()

        # ── 2. TRANSFORM ────────────────────────────────────────────────────
        transformer = Transformer(
            valid_statuses=config.VALID_ORDER_STATUSES,
            valid_channels=config.VALID_CHANNELS,
            max_discount=config.MAX_DISCOUNT_PCT,
            min_price=config.MIN_PRICE,
        )
        cleaned, dq_report = transformer.transform_all(datasets)

        if dry_run:
            logger.info("\n⏭️  DRY RUN: Skipping Load and Report phases.")
            logger.info("✅ Dry run complete. Data looks good!")
            return

        # ── 3. LOAD ─────────────────────────────────────────────────────────
        loader = Loader(
            database_url=config.DATABASE_URL,
            sql_dir=config.SQL_DIR,
        )
        loader.load_all(cleaned, config.PROCESSED_DATA_DIR)

        # ── 4. REPORT ───────────────────────────────────────────────────────
        if not skip_report:
            reporter = ReportGenerator(
                engine=loader.engine,
                reports_dir=config.REPORTS_DIR,
            )
            report_path = reporter.generate()
            logger.info(f"\n  📊 Report ready → open in browser: {report_path}")

        elapsed = time.time() - start_time
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"🎉 Pipeline completed successfully in {elapsed:.1f}s")
        logger.info("=" * 60)

    except FileNotFoundError as e:
        logger.error(f"\n❌ File Error: {e}")
        logger.error("   → Have you run 'python generate_data.py' first?")
        sys.exit(1)

    except Exception as e:
        logger.error(f"\n❌ Pipeline failed: {type(e).__name__}: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E-Commerce ETL Pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate extract+transform only, no DB writes")
    parser.add_argument("--no-report", action="store_true",
                        help="Skip HTML report generation")
    args = parser.parse_args()

    run_pipeline(dry_run=args.dry_run, skip_report=args.no_report)
