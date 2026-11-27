"""Render a tender comparison as a plain HTML page.

No JavaScript, no framework. One page, three tables: the ranking,
the totals by trade, and every item with each bidder's rate next to
the median. Outlier rates are highlighted so they jump out.
"""

import html

from .compare import Comparison


def _money(value: float) -> str:
    return f"${value:,.2f}"


def render_html(comparison: Comparison) -> str:
    rows = []
    rows.append("<!DOCTYPE html>")
    rows.append('<html lang="en">')
    rows.append("<head>")
    rows.append('<meta charset="utf-8">')
    rows.append("<title>Tender comparison</title>")
    rows.append("<style>")
    rows.append(
        "body { font-family: system-ui, sans-serif; margin: 2em; "
        "color: #222; } "
        "table { border-collapse: collapse; margin: 1em 0 2em; } "
        "th, td { border: 1px solid #ccc; padding: 6px 10px; "
        "text-align: right; } "
        "th:first-child, td:first-child, th:nth-child(2), "
        "td:nth-child(2) { text-align: left; } "
        "th { background: #f0f0f0; } "
        ".outlier-high { background: #fde8e8; font-weight: bold; } "
        ".outlier-low { background: #e8f0fd; font-weight: bold; } "
        ".rank1 { font-weight: bold; }"
    )
    rows.append("</style>")
    rows.append("</head>")
    rows.append("<body>")
    rows.append("<h1>Tender comparison</h1>")
    rows.append(
        f"<p>{len(comparison.bidders)} bidders compared. "
        f"Lowest total {html.escape(_money(comparison.lowest_total))}, "
        f"highest {html.escape(_money(comparison.highest_total))}, "
        f"a spread of {comparison.spread_pct:.1f}%.</p>"
    )

    rows.append("<h2>Ranking by total</h2>")
    rows.append("<table>")
    rows.append("<tr><th>Rank</th><th>Bidder</th><th>Total</th></tr>")
    for bidder in comparison.bidders:
        css = ' class="rank1"' if bidder.rank == 1 else ""
        rows.append(
            f"<tr{css}><td>{bidder.rank}</td>"
            f"<td>{html.escape(bidder.name)}</td>"
            f"<td>{_money(bidder.total)}</td></tr>"
        )
    rows.append("</table>")

    rows.append("<h2>Totals by trade</h2>")
    rows.append("<table>")
    header = "<tr><th>Trade</th>" + "".join(
        f"<th>{html.escape(bidder.name)}</th>"
        for bidder in comparison.bidders
    )
    rows.append(header + "</tr>")
    trades: list[str] = []
    for bidder in comparison.bidders:
        for trade in bidder.totals_by_trade:
            if trade not in trades:
                trades.append(trade)
    for trade in sorted(trades):
        cells = "".join(
            f"<td>{_money(bidder.totals_by_trade.get(trade, 0.0))}</td>"
            for bidder in comparison.bidders
        )
        rows.append(f"<tr><td>{html.escape(trade)}</td>{cells}</tr>")
    rows.append("</table>")

    if comparison.outliers:
        rows.append("<h2>Rates to look at</h2>")
        rows.append(
            "<p>These rates sit more than 25% away from the median "
            "rate for the same item. High ones cost you money. Low "
            "ones can mean a missed scope or a mistake.</p>"
        )
        rows.append("<table>")
        rows.append(
            "<tr><th>Item</th><th>Description</th><th>Bidder</th>"
            "<th>Rate</th><th>Median</th><th>Difference</th></tr>"
        )
        for outlier in comparison.outliers:
            sign = "+" if outlier.difference_pct > 0 else ""
            rows.append(
                f"<tr><td>{html.escape(outlier.item_no)}</td>"
                f"<td>{html.escape(outlier.description)}</td>"
                f"<td>{html.escape(outlier.bidder)}</td>"
                f"<td>{_money(outlier.rate)}</td>"
                f"<td>{_money(outlier.median)}</td>"
                f"<td>{sign}{outlier.difference_pct:.1f}% "
                f"({outlier.direction})</td></tr>"
            )
        rows.append("</table>")
    else:
        rows.append("<h2>Rates to look at</h2>")
        rows.append("<p>No rate sits more than 25% from its median.</p>")

    rows.append("<h2>Item by item</h2>")
    rows.append("<table>")
    header = (
        "<tr><th>Item</th><th>Description</th><th>Trade</th>"
        "<th>Unit</th><th>Qty</th>"
    )
    for bidder in comparison.bidders:
        header += f"<th>{html.escape(bidder.name)}</th>"
    header += "<th>Median</th></tr>"
    rows.append(header)
    for item in comparison.items:
        cells = f"<tr><td>{html.escape(item.item_no)}</td>"
        cells += f"<td>{html.escape(item.description)}</td>"
        cells += f"<td>{html.escape(item.trade)}</td>"
        cells += f"<td>{html.escape(item.unit)}</td>"
        cells += f"<td>{item.quantity:g}</td>"
        flagged = {outlier.bidder for outlier in item.outliers}
        for bidder in comparison.bidders:
            rate = item.rates.get(bidder.name)
            if rate is None:
                cells += "<td>not priced</td>"
                continue
            css = ""
            if bidder.name in flagged:
                direction = next(
                    outlier.direction
                    for outlier in item.outliers
                    if outlier.bidder == bidder.name
                )
                css = f' class="outlier-{direction}"'
            cells += f"<td{css}>{_money(rate)}</td>"
        median = _money(item.median) if item.median is not None else "-"
        cells += f"<td>{median}</td></tr>"
        rows.append(cells)
    rows.append("</table>")
    rows.append("</body>")
    rows.append("</html>")
    return "\n".join(rows)
