# tender-compare

Comparing priced BOQs by hand takes hours. You open three or four spreadsheets, flip between them, and try to spot the one rate that is way out of line. I built this to do that work in seconds.

You upload one CSV per bidder, and it ranks the bidders by total price, breaks the totals down by trade, and flags any rate that sits more than 25% away from the median rate for the same item. High rates cost you money. Low rates can mean a missed scope or a mistake. Both are worth a second look before you award the job.

## What it does

- Reads one CSV per bidder, with columns `item_no`, `description`, `trade`, `unit`, `quantity`, `rate`.
- Matches items across bidders by item number, so everyone prices the same list.
- Ranks bidders by total price, lowest first, and shows the spread between lowest and highest.
- Shows totals by trade, so you can see which bidder is cheap on concrete and expensive on formwork.
- Flags rate outliers: any rate more than 25% above or below the median rate for that item.
- Serves the result as a web page, or as JSON if you want to feed it into something else.

## Quick start

You need Python 3.10 or later.

```bash
pip install -r requirements.txt
uvicorn tender_compare.app:app --reload
```

Then open http://127.0.0.1:8000 in your browser, pick two or more bidder CSVs, and hit Compare tenders.

To get JSON instead, post the same files to `/api/compare`:

```bash
curl -F "files=@examples/alpha-builders.csv" \
     -F "files=@examples/beta-construction.csv" \
     -F "files=@examples/gamma-works.csv" \
     http://127.0.0.1:8000/api/compare
```

Bidder names come from the file names by default. You can pass your own with a `bidder_names` form field, one name per file, in the same order.

## Sample data

The three files in `examples/` are sample data for a single storey house, priced by three made up bidders in Singapore dollars. They are not real tenders. I planted two outliers on purpose so you can see the flagging work:

- Beta Construction prices formwork to beams and columns at $165 per m2, against a median of $95. That is about 74% high, and it gets flagged.
- Gamma Works prices Concrete Grade 30 at $148 per m3, against a median of $215. That is about 31% low, and it gets flagged.

On the sample data the ranking comes out Gamma Works first at $209,242, Alpha Builders second at $226,230, and Beta Construction third at $262,036. The spread from lowest to highest is about 25%.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## Scope note

This is a portfolio project, and I am honest about what it is not. It compares prices, it does not judge quality, past performance, or whether a bidder can actually do the work. It assumes every bidder priced the same item list with the same quantities. It does not handle provisional sums, prime cost sums, or alternative tenders. The 25% outlier threshold is a starting point, not a rule from any standard. If you use it on a real tender, check the flagged rates by hand before you act on them.
