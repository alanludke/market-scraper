from .vtex import VTEXScraper
from .carrefour_html import CarrefourHTMLScraper

SCRAPER_REGISTRY = {
    "vtex": VTEXScraper,
    "carrefour_html": CarrefourHTMLScraper,
}
