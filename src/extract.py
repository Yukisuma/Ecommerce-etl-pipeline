"""
src/extract.py — Extract phase: Load raw CSV files into DataFrames
"""

import logging
import pandas as pd
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class Extractor:
    """
    Reads raw CSV files from the data/raw directory.
    Validates that required files and columns are present.
    """

    def __init__(self, raw_dir: Path, expected_columns: Dict[str, list]):
        self.raw_dir = raw_dir
        self.expected_columns = expected_columns

    def load_csv(self, name: str) -> pd.DataFrame:
        """Load a single CSV file by its logical name (e.g. 'orders')."""
        filepath = self.raw_dir / f"{name}.csv"
        if not filepath.exists():
            raise FileNotFoundError(f"[Extractor] Missing CSV file: {filepath}")

        df = pd.read_csv(filepath, dtype=str, keep_default_na=False)
        logger.info(f"  📂 Loaded '{name}.csv' → {len(df):,} rows, {len(df.columns)} columns")

        # Column validation
        expected = set(self.expected_columns.get(name, []))
        actual = set(df.columns)
        missing = expected - actual
        extra = actual - expected
        if missing:
            raise ValueError(f"[Extractor] '{name}.csv' is missing columns: {missing}")
        if extra:
            logger.warning(f"  ⚠️  '{name}.csv' has unexpected columns (will keep): {extra}")

        return df

    def extract_all(self) -> Dict[str, pd.DataFrame]:
        """Load all required CSV files and return as a dictionary of DataFrames."""
        logger.info("=" * 60)
        logger.info("📥  EXTRACT PHASE — Reading Raw CSV Files")
        logger.info("=" * 60)

        datasets = {}
        for name in self.expected_columns.keys():
            datasets[name] = self.load_csv(name)

        total_rows = sum(len(df) for df in datasets.values())
        logger.info(f"  ✅ Extraction complete. Total rows ingested: {total_rows:,}")
        return datasets
