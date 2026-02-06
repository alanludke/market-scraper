"""
Parquet writer helper for efficient columnar storage.

Features:
- DataFrame conversion from VTEX API responses
- Snappy compression (fast, ~80-90% size reduction)
- Schema inference with type hints
- Metadata injection (run_id, supermarket, region)
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger


def write_parquet(
    items: List[Dict[str, Any]],
    output_path: Path,
    metadata: Dict[str, Any] = None,
    compression: str = "snappy"
) -> int:
    """
    Write list of items to Parquet file with metadata injection.

    Args:
        items: List of product dictionaries (VTEX API response)
        output_path: Path to output .parquet file
        metadata: Optional metadata to inject into each record
        compression: Compression codec (snappy, gzip, zstd)

    Returns:
        Number of records written

    Example:
        >>> items = [{"productId": "123", "productName": "Apple", "price": 5.99}]
        >>> metadata = {"run_id": "20260205_143200", "supermarket": "bistek"}
        >>> write_parquet(items, Path("output.parquet"), metadata)
        1
    """
    if not items:
        logger.warning(f"No items to write to {output_path}")
        return 0

    # Inject metadata into each item
    if metadata:
        for item in items:
            if "_metadata" not in item:
                item["_metadata"] = {}
            item["_metadata"].update(metadata)

    # Convert to DataFrame
    try:
        df = pd.json_normalize(items, sep="_")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write Parquet with compression
        df.to_parquet(
            output_path,
            engine="pyarrow",
            compression=compression,
            index=False
        )

        logger.debug(f"Wrote {len(df)} records to {output_path.name} ({compression} compression)")
        return len(df)

    except Exception as e:
        logger.error(f"Failed to write Parquet to {output_path}: {e}")
        raise


def consolidate_parquet_files(
    input_dir: Path,
    output_file: Path,
    pattern: str = "*.parquet",
    delete_batches: bool = True
) -> int:
    """
    Consolidate multiple Parquet batch files into a single file.

    Args:
        input_dir: Directory containing batch Parquet files
        output_file: Output consolidated Parquet file
        pattern: Glob pattern for batch files
        delete_batches: If True, delete batch files after successful consolidation

    Returns:
        Total number of records consolidated
    """
    batch_files = sorted(input_dir.glob(pattern))

    if not batch_files:
        logger.warning(f"No Parquet files found in {input_dir} with pattern {pattern}")
        return 0

    # Read all batches into a single DataFrame
    dfs = []
    for batch_file in batch_files:
        try:
            df = pd.read_parquet(batch_file, engine="pyarrow")
            dfs.append(df)
        except Exception as e:
            logger.error(f"Failed to read {batch_file}: {e}")
            continue

    if not dfs:
        logger.error("No valid Parquet files could be read")
        return 0

    # Concatenate and write
    consolidated = pd.concat(dfs, ignore_index=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    consolidated.to_parquet(
        output_file,
        engine="pyarrow",
        compression="snappy",
        index=False
    )

    logger.info(f"Consolidated {len(dfs)} files -> {output_file.name} ({len(consolidated)} records)")

    # Delete batch files after successful consolidation
    if delete_batches:
        for batch_file in batch_files:
            try:
                batch_file.unlink()
                logger.debug(f"Deleted batch file: {batch_file.name}")
            except Exception as e:
                logger.warning(f"Failed to delete {batch_file.name}: {e}")

        # Also delete the batches directory if empty
        try:
            if input_dir.exists() and not any(input_dir.iterdir()):
                input_dir.rmdir()
                logger.debug(f"Deleted empty batches directory: {input_dir}")
        except Exception as e:
            logger.debug(f"Could not delete batches dir: {e}")

    return len(consolidated)
