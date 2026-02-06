"""
EAN watermark management for incremental enrichment.

Tracks which EANs have already been enriched from OpenFoodFacts API,
enabling incremental updates that only fetch new EANs.
"""

import json
from pathlib import Path
from typing import Set, List


class EANWatermark:
    """
    Track already enriched EANs to enable incremental updates.

    The watermark is stored as a JSON file containing a sorted list of EAN codes
    that have already been fetched from OpenFoodFacts API.

    Example:
        watermark = EANWatermark()
        enriched_eans = watermark.load()
        new_eans = watermark.get_new_eans(current_eans)
        watermark.save(all_eans)
    """

    def __init__(self, watermark_path: str = "data/metadata/ean_enrichment_watermark.json"):
        """
        Initialize watermark manager.

        Args:
            watermark_path: Path to watermark JSON file (default: data/metadata/ean_enrichment_watermark.json)
        """
        self.watermark_path = Path(watermark_path)
        self.watermark_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Set[str]:
        """
        Load enriched EANs from watermark file.

        Returns:
            Set of EAN codes that have already been enriched.
            Empty set if watermark file doesn't exist.
        """
        if not self.watermark_path.exists():
            return set()

        with open(self.watermark_path, 'r', encoding='utf-8') as f:
            return set(json.load(f))

    def save(self, eans: List[str]) -> None:
        """
        Save enriched EANs to watermark file.

        The EANs are sorted before saving for readability and consistency.

        Args:
            eans: List of EAN codes to save in watermark
        """
        with open(self.watermark_path, 'w', encoding='utf-8') as f:
            json.dump(sorted(eans), f, indent=2, ensure_ascii=False)

    def get_new_eans(self, current_eans: List[str]) -> List[str]:
        """
        Return EANs not yet enriched.

        Compares current EAN list against watermark to identify net-new EANs
        that need to be fetched from OpenFoodFacts API.

        Args:
            current_eans: List of current EAN codes from VTEX products

        Returns:
            List of EANs that are not in the watermark (need enrichment)
        """
        enriched = self.load()
        return [ean for ean in current_eans if ean not in enriched]

    def get_stats(self) -> dict:
        """
        Get watermark statistics.

        Returns:
            Dictionary with watermark stats (ean_count, exists)
        """
        enriched = self.load()
        return {
            "ean_count": len(enriched),
            "exists": self.watermark_path.exists(),
            "path": str(self.watermark_path)
        }
