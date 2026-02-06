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


def _clean_empty_structs(obj: Any) -> Any:
    """
    Recursively remove empty dict/struct fields from nested data.

    PyArrow cannot serialize empty struct types (dicts with no keys) to Parquet.
    This function removes them before serialization.

    Args:
        obj: Any Python object (dict, list, primitive)

    Returns:
        Cleaned object with empty dicts removed

    Example:
        >>> data = {"a": 1, "b": {}, "c": {"d": {}}}
        >>> _clean_empty_structs(data)
        {"a": 1, "c": {}}
    """
    if isinstance(obj, dict):
        # Remove keys with empty dict values, recursively clean others
        cleaned = {}
        for key, value in obj.items():
            if isinstance(value, dict) and not value:
                # Skip empty dicts (empty structs)
                continue
            else:
                # Recursively clean the value
                cleaned[key] = _clean_empty_structs(value)
        return cleaned

    elif isinstance(obj, list):
        # Recursively clean list elements
        return [_clean_empty_structs(item) for item in obj]

    else:
        # Primitives (str, int, float, bool, None) - return as-is
        return obj


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

    # Clean empty structs before DataFrame conversion
    # PyArrow cannot serialize empty dicts (structs with no child fields)
    cleaned_items = [_clean_empty_structs(item) for item in items]

    # Convert to DataFrame
    try:
        df = pd.json_normalize(cleaned_items, sep="_")

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
