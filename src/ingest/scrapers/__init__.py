from .vtex import VTEXScraper
from .carrefour_html import CarrefourHTMLScraper
from .angeloni_html import AngeloniHTMLScraper
from .superkoch_html import SuperKochHTMLScraper
from .hippo_html import HippoHTMLScraper

SCRAPER_REGISTRY = {
    "vtex": VTEXScraper,
    "carrefour_html": CarrefourHTMLScraper,
    "angeloni_html": AngeloniHTMLScraper,
    "superkoch_html": SuperKochHTMLScraper,
    "hippo_html": HippoHTMLScraper,
}
