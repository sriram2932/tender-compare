"""Compare priced BOQs from several bidders, line by line.

I built this because comparing tenders by hand takes hours. You open
three or four spreadsheets, flip between them, and try to spot the one
rate that is way out of line. This does that work in seconds.

Each bidder submits one CSV. Items are matched by item number, totals
are ranked, and any rate more than 25 percent away from the median
rate for that item is flagged.
"""

from .compare import (
    Bidder,
    Comparison,
    Item,
    ItemComparison,
    Outlier,
    compare_bidders,
    median_rate,
    parse_bidder_csv,
)
from .report import render_html

__all__ = [
    "Bidder",
    "Comparison",
    "Item",
    "ItemComparison",
    "Outlier",
    "compare_bidders",
    "median_rate",
    "parse_bidder_csv",
    "render_html",
]

__version__ = "1.0.0"
