"""Parse bidder CSVs and compare them.

One CSV per bidder. Columns are: item_no, description, trade, unit,
quantity, rate. Items are matched across bidders by item number, so
every bidder must use the same item numbers for the same work. That
is how a real priced BOQ works: the client issues the item list and
each bidder prices it.
"""

import csv
import io
import statistics
from dataclasses import dataclass, field

REQUIRED_COLUMNS = {"item_no", "description", "trade", "unit", "quantity", "rate"}

OUTLIER_THRESHOLD = 0.25


@dataclass
class Item:
    """One priced line in a bidder's BOQ."""

    item_no: str
    description: str
    trade: str
    unit: str
    quantity: float
    rate: float

    @property
    def amount(self) -> float:
        return self.quantity * self.rate


@dataclass
class Bidder:
    """One bidder's full priced BOQ."""

    name: str
    items: list[Item] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(item.amount for item in self.items)

    @property
    def totals_by_trade(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for item in self.items:
            totals[item.trade] = totals.get(item.trade, 0.0) + item.amount
        return totals


@dataclass
class Outlier:
    """One rate that sits far from the median rate for its item."""

    item_no: str
    description: str
    bidder: str
    rate: float
    median: float
    difference_pct: float

    @property
    def direction(self) -> str:
        return "high" if self.difference_pct > 0 else "low"


@dataclass
class ItemComparison:
    """How every bidder priced one item, against the median."""

    item_no: str
    description: str
    trade: str
    unit: str
    quantity: float
    rates: dict[str, float]
    median: float | None
    outliers: list[Outlier] = field(default_factory=list)


@dataclass
class BidderSummary:
    name: str
    total: float
    rank: int
    totals_by_trade: dict[str, float]


@dataclass
class Comparison:
    """The full result of comparing two or more bidders."""

    bidders: list[BidderSummary]
    items: list[ItemComparison]
    outliers: list[Outlier]

    @property
    def ranking(self) -> list[str]:
        return [bidder.name for bidder in self.bidders]

    @property
    def lowest_total(self) -> float:
        return self.bidders[0].total if self.bidders else 0.0

    @property
    def highest_total(self) -> float:
        return self.bidders[-1].total if self.bidders else 0.0

    @property
    def spread_pct(self) -> float:
        if not self.bidders or self.lowest_total == 0:
            return 0.0
        return (self.highest_total - self.lowest_total) / self.lowest_total * 100


def parse_bidder_csv(name: str, text: str) -> Bidder:
    """Parse one bidder's CSV text into a Bidder.

    Raises ValueError with a plain message when the file is missing a
    column, has no priced rows, or has a number that cannot be read.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError(f"{name}: the file is empty.")
    columns = {column.strip().lower() for column in reader.fieldnames}
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(
            f"{name}: missing column(s): {', '.join(sorted(missing))}."
        )

    bidder = Bidder(name=name)
    for row_number, row in enumerate(reader, start=2):
        values = {key.strip().lower(): (value or "").strip() for key, value in row.items() if key}
        if not values.get("item_no"):
            continue
        try:
            quantity = float(values["quantity"])
            rate = float(values["rate"])
        except ValueError:
            raise ValueError(
                f"{name}: row {row_number} has a quantity or rate "
                "that is not a number."
            )
        bidder.items.append(
            Item(
                item_no=values["item_no"],
                description=values["description"],
                trade=values["trade"],
                unit=values["unit"],
                quantity=quantity,
                rate=rate,
            )
        )
    if not bidder.items:
        raise ValueError(f"{name}: no priced items found in the file.")
    return bidder


def median_rate(rates: list[float]) -> float | None:
    """The median of a list of rates, or None when the list is empty."""
    if not rates:
        return None
    return float(statistics.median(rates))


def compare_bidders(bidders: list[Bidder]) -> Comparison:
    """Compare two or more bidders and rank them by total price.

    The lowest total ranks first. A rate is flagged as an outlier when
    it differs from the median rate for that item by more than 25
    percent, in either direction.
    """
    if len(bidders) < 2:
        raise ValueError("Need at least two bidders to compare.")

    ranked = sorted(bidders, key=lambda bidder: bidder.total)
    summaries = [
        BidderSummary(
            name=bidder.name,
            total=bidder.total,
            rank=index + 1,
            totals_by_trade=bidder.totals_by_trade,
        )
        for index, bidder in enumerate(ranked)
    ]

    item_numbers: list[str] = []
    for bidder in bidders:
        for item in bidder.items:
            if item.item_no not in item_numbers:
                item_numbers.append(item.item_no)
    item_numbers.sort()

    by_bidder: dict[str, dict[str, Item]] = {
        bidder.name: {item.item_no: item for item in bidder.items}
        for bidder in bidders
    }

    item_comparisons: list[ItemComparison] = []
    all_outliers: list[Outlier] = []
    for item_no in item_numbers:
        priced = [
            (bidder.name, by_bidder[bidder.name][item_no])
            for bidder in bidders
            if item_no in by_bidder[bidder.name]
        ]
        first = priced[0][1]
        rates = {name: item.rate for name, item in priced}
        median = median_rate(list(rates.values()))
        outliers: list[Outlier] = []
        if median is not None and median != 0:
            for name, item in priced:
                difference_pct = (item.rate - median) / median * 100
                if abs(difference_pct) > OUTLIER_THRESHOLD * 100:
                    outliers.append(
                        Outlier(
                            item_no=item_no,
                            description=first.description,
                            bidder=name,
                            rate=item.rate,
                            median=median,
                            difference_pct=round(difference_pct, 1),
                        )
                    )
        item_comparisons.append(
            ItemComparison(
                item_no=item_no,
                description=first.description,
                trade=first.trade,
                unit=first.unit,
                quantity=first.quantity,
                rates=rates,
                median=median,
                outliers=outliers,
            )
        )
        all_outliers.extend(outliers)

    return Comparison(
        bidders=summaries, items=item_comparisons, outliers=all_outliers
    )


def comparison_to_dict(comparison: Comparison) -> dict:
    """Turn a Comparison into plain data for the JSON endpoint."""
    return {
        "ranking": [
            {
                "rank": bidder.rank,
                "name": bidder.name,
                "total": round(bidder.total, 2),
                "totals_by_trade": {
                    trade: round(amount, 2)
                    for trade, amount in bidder.totals_by_trade.items()
                },
            }
            for bidder in comparison.bidders
        ],
        "lowest_total": round(comparison.lowest_total, 2),
        "highest_total": round(comparison.highest_total, 2),
        "spread_pct": round(comparison.spread_pct, 1),
        "items": [
            {
                "item_no": item.item_no,
                "description": item.description,
                "trade": item.trade,
                "unit": item.unit,
                "quantity": item.quantity,
                "rates": item.rates,
                "median_rate": item.median,
                "outliers": [
                    {
                        "bidder": outlier.bidder,
                        "rate": outlier.rate,
                        "difference_pct": outlier.difference_pct,
                        "direction": outlier.direction,
                    }
                    for outlier in item.outliers
                ],
            }
            for item in comparison.items
        ],
        "outliers": [
            {
                "item_no": outlier.item_no,
                "description": outlier.description,
                "bidder": outlier.bidder,
                "rate": outlier.rate,
                "median_rate": outlier.median,
                "difference_pct": outlier.difference_pct,
                "direction": outlier.direction,
            }
            for outlier in comparison.outliers
        ],
    }
