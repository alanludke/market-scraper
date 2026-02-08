"""
Integration tests for Parquet file I/O operations.

Tests:
- Batch writing
- Batch consolidation
- Schema consistency
- Metadata preservation
- Partition handling
"""

import pytest
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime


class TestParquetBatchOperations:
    """Test Parquet batch file operations."""

    @pytest.fixture
    def sample_product_df(self):
        """Sample product DataFrame."""
        return pd.DataFrame([
            {
                "productId": "1",
                "productName": "Product A",
                "price": 10.50,
                "brand": "Brand X",
                "scrapedAt": "2026-02-07T10:00:00"
            },
            {
                "productId": "2",
                "productName": "Product B",
                "price": 25.99,
                "brand": "Brand Y",
                "scrapedAt": "2026-02-07T10:00:00"
            }
        ])

    def test_write_parquet_batch(self, sample_product_df, temp_dir):
        """Test writing DataFrame to Parquet."""
        output_file = temp_dir / "batch_001.parquet"

        # Write
        sample_product_df.to_parquet(output_file, index=False)

        # Verify
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_read_parquet_batch(self, sample_product_df, temp_dir):
        """Test reading Parquet back to DataFrame."""
        output_file = temp_dir / "batch_002.parquet"

        # Write
        sample_product_df.to_parquet(output_file, index=False)

        # Read
        df_read = pd.read_parquet(output_file)

        # Verify
        assert len(df_read) == len(sample_product_df)
        assert list(df_read.columns) == list(sample_product_df.columns)
        pd.testing.assert_frame_equal(df_read, sample_product_df)

    def test_parquet_compression(self, sample_product_df, temp_dir):
        """Test Parquet compression reduces file size."""
        file_uncompressed = temp_dir / "uncompressed.parquet"
        file_compressed = temp_dir / "compressed.parquet"

        # Write uncompressed
        sample_product_df.to_parquet(file_uncompressed, compression='none', index=False)

        # Write compressed (snappy default)
        sample_product_df.to_parquet(file_compressed, compression='snappy', index=False)

        # Verify compression reduces size (or is similar for small datasets)
        assert file_compressed.stat().st_size <= file_uncompressed.stat().st_size


class TestParquetSchemaValidation:
    """Test Parquet schema consistency."""

    def test_schema_preserved_after_write(self, temp_dir):
        """Test schema is preserved in Parquet files."""
        df = pd.DataFrame({
            "productId": pd.Series(["1", "2"], dtype="string"),
            "price": pd.Series([10.50, 25.99], dtype="float64"),
            "available": pd.Series([True, False], dtype="bool"),
            "scrapedAt": pd.Series(["2026-02-07T10:00:00", "2026-02-07T11:00:00"], dtype="string")
        })

        output_file = temp_dir / "schema_test.parquet"
        df.to_parquet(output_file, index=False)

        # Read back
        df_read = pd.read_parquet(output_file)

        # Verify dtypes
        assert df_read["productId"].dtype == "object" or str(df_read["productId"].dtype) == "string"
        assert df_read["price"].dtype == "float64"
        assert df_read["available"].dtype == "bool"

    def test_handle_missing_values(self, temp_dir):
        """Test Parquet handles missing/null values."""
        df = pd.DataFrame({
            "productId": ["1", "2", "3"],
            "brand": ["Brand A", None, "Brand C"],
            "price": [10.0, 20.0, None]
        })

        output_file = temp_dir / "nulls_test.parquet"
        df.to_parquet(output_file, index=False)

        df_read = pd.read_parquet(output_file)

        # Verify nulls preserved
        assert df_read["brand"].isna().sum() == 1
        assert df_read["price"].isna().sum() == 1

    def test_nested_json_columns(self, temp_dir):
        """Test Parquet handles JSON/nested columns."""
        df = pd.DataFrame({
            "productId": ["1", "2"],
            "categories": [["Cat A", "Cat B"], ["Cat C"]],
            "metadata": [{"key": "value1"}, {"key": "value2"}]
        })

        output_file = temp_dir / "nested_test.parquet"
        df.to_parquet(output_file, index=False)

        df_read = pd.read_parquet(output_file)

        # Verify lists/dicts preserved
        assert isinstance(df_read["categories"].iloc[0], list)
        assert len(df_read["categories"].iloc[0]) == 2


class TestParquetConsolidation:
    """Test consolidating multiple Parquet batches."""

    def test_consolidate_multiple_batches(self, temp_dir):
        """Test combining multiple batch files."""
        batches_dir = temp_dir / "batches"
        batches_dir.mkdir()

        # Create 3 batch files
        for i in range(3):
            df = pd.DataFrame({
                "productId": [f"{i}_{j}" for j in range(10)],
                "productName": [f"Product {i}_{j}" for j in range(10)],
                "price": [(i+1) * 10 + j for j in range(10)]
            })
            batch_file = batches_dir / f"batch_{i+1:04d}.parquet"
            df.to_parquet(batch_file, index=False)

        # Consolidate
        all_dfs = []
        for batch_file in sorted(batches_dir.glob("*.parquet")):
            all_dfs.append(pd.read_parquet(batch_file))

        consolidated = pd.concat(all_dfs, ignore_index=True)

        # Write consolidated
        final_file = temp_dir / "consolidated.parquet"
        consolidated.to_parquet(final_file, index=False)

        # Verify
        df_final = pd.read_parquet(final_file)
        assert len(df_final) == 30  # 3 batches * 10 products each
        assert "productId" in df_final.columns

    def test_consolidation_preserves_schema(self, temp_dir):
        """Test consolidation maintains consistent schema."""
        batches_dir = temp_dir / "batches"
        batches_dir.mkdir()

        schema_df = pd.DataFrame({
            "productId": pd.Series([], dtype="string"),
            "price": pd.Series([], dtype="float64"),
            "available": pd.Series([], dtype="bool")
        })

        # Create batches with same schema
        for i in range(2):
            df = pd.DataFrame({
                "productId": [str(i), str(i+1)],
                "price": [float(i*10), float((i+1)*10)],
                "available": [True, False]
            })
            batch_file = batches_dir / f"batch_{i:04d}.parquet"
            df.to_parquet(batch_file, index=False)

        # Consolidate
        dfs = [pd.read_parquet(f) for f in sorted(batches_dir.glob("*.parquet"))]
        consolidated = pd.concat(dfs, ignore_index=True)

        # Verify schema consistency
        assert consolidated["price"].dtype == "float64"
        assert consolidated["available"].dtype == "bool"


class TestParquetMetadata:
    """Test Parquet metadata and partitioning."""

    def test_write_metadata_to_parquet(self, temp_dir):
        """Test writing custom metadata."""
        df = pd.DataFrame({
            "productId": ["1", "2"],
            "price": [10.0, 20.0]
        })

        output_file = temp_dir / "with_metadata.parquet"

        # Write with metadata
        table = pa.Table.from_pandas(df)
        metadata = {
            b"store": b"bistek",
            b"region": b"florianopolis",
            b"scraped_at": b"2026-02-07"
        }
        merged_metadata = {**table.schema.metadata, **metadata} if table.schema.metadata else metadata
        table = table.replace_schema_metadata(merged_metadata)

        pq.write_table(table, output_file)

        # Read and verify metadata
        parquet_file = pq.ParquetFile(output_file)
        file_metadata = parquet_file.schema_arrow.metadata

        assert b"store" in file_metadata
        assert file_metadata[b"store"] == b"bistek"

    def test_partitioned_dataset(self, temp_dir):
        """Test writing partitioned Parquet dataset."""
        df = pd.DataFrame({
            "productId": ["1", "2", "3", "4"],
            "productName": ["A", "B", "C", "D"],
            "store": ["bistek", "bistek", "fort", "fort"],
            "price": [10, 20, 30, 40]
        })

        output_dir = temp_dir / "partitioned"

        # Write partitioned by store
        df.to_parquet(
            output_dir,
            partition_cols=["store"],
            index=False
        )

        # Verify partitions created
        assert (output_dir / "store=bistek").exists()
        assert (output_dir / "store=fort").exists()

        # Read back
        df_read = pd.read_parquet(output_dir)
        assert len(df_read) == 4


class TestParquetPerformance:
    """Test Parquet performance characteristics."""

    def test_large_dataset_write_performance(self, temp_dir):
        """Test writing large dataset is performant."""
        import time

        # Create large dataset (10k rows)
        df = pd.DataFrame({
            "productId": [str(i) for i in range(10000)],
            "productName": [f"Product {i}" for i in range(10000)],
            "price": [float(i % 100) for i in range(10000)],
            "brand": [f"Brand {i % 50}" for i in range(10000)]
        })

        output_file = temp_dir / "large_dataset.parquet"

        start = time.time()
        df.to_parquet(output_file, index=False)
        elapsed = time.time() - start

        # Should complete in reasonable time (< 1 second for 10k rows)
        assert elapsed < 1.0, f"Write took {elapsed:.2f}s (too slow)"
        assert output_file.exists()

    def test_columnar_storage_efficiency(self, temp_dir):
        """Test columnar storage is space-efficient."""
        # Create dataset with repetitive values (good for columnar compression)
        df = pd.DataFrame({
            "productId": [str(i) for i in range(1000)],
            "brand": ["Same Brand"] * 1000,  # Repetitive
            "category": ["Same Category"] * 1000,  # Repetitive
            "price": [9.99] * 1000  # Repetitive
        })

        output_file = temp_dir / "columnar_test.parquet"
        df.to_parquet(output_file, compression='snappy', index=False)

        # File should be compressed well (< 50KB for this dataset)
        file_size = output_file.stat().st_size
        assert file_size < 50000, f"File too large: {file_size} bytes"


class TestParquetDataQuality:
    """Test data quality checks on Parquet files."""

    def test_detect_duplicate_product_ids(self, temp_dir):
        """Test detecting duplicate product IDs in Parquet."""
        df = pd.DataFrame({
            "productId": ["1", "2", "2", "3"],  # Duplicate ID
            "productName": ["A", "B", "B_dup", "C"]
        })

        output_file = temp_dir / "duplicates.parquet"
        df.to_parquet(output_file, index=False)

        # Read and check
        df_read = pd.read_parquet(output_file)
        duplicates = df_read[df_read.duplicated(subset=["productId"], keep=False)]

        assert len(duplicates) == 2, "Should detect 2 duplicate rows"

    def test_validate_price_ranges(self, temp_dir):
        """Test validating price data in Parquet."""
        df = pd.DataFrame({
            "productId": ["1", "2", "3"],
            "price": [10.0, -5.0, 1000000.0]  # Invalid: negative, extreme
        })

        output_file = temp_dir / "price_validation.parquet"
        df.to_parquet(output_file, index=False)

        df_read = pd.read_parquet(output_file)

        # Validate
        invalid_prices = df_read[(df_read["price"] < 0) | (df_read["price"] > 100000)]
        assert len(invalid_prices) == 2, "Should find 2 invalid prices"
