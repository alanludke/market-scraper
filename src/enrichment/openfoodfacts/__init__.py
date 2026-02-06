"""
OpenFoodFacts enrichment module.

Enriches product EAN codes with canonical names, nutritional data (Nutriscore),
and product attributes from the OpenFoodFacts global database.

Main components:
    - enricher.EANEnrichmentPipeline: Main pipeline for fetching EAN data from API
    - watermark.EANWatermark: Incremental tracking of enriched EANs
"""

from .enricher import EANEnrichmentPipeline
from .watermark import EANWatermark

__all__ = ['EANEnrichmentPipeline', 'EANWatermark']
