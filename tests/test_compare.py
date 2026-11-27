"""Tests for tender-compare.

Covers CSV parsing, totals, ranking, outlier flagging, and both
endpoints. The sample files in examples/ are used for the endpoint
tests, so the numbers below come from real runs of the app.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tender_compare.app import app
from tender_compare.compare import (
    Bidder,
    compare_bidders,
    median_rate,
    parse_bidder_csv,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

SMALL_CSV = """item_no,description,trade,unit,quantity,rate
A1,Site establishment,Preliminaries,lot,1,5000
B1,Excavation,Earthworks,m3,100,20
"""

SECOND_CSV = """item_no,description,trade,unit,quantity,rate
A1,Site establishment,Preliminaries,lot,1,6000
B1,Excavation,Earthworks,m3,100,24
"""


def load_example(name: str) -> tuple[str, bytes]:
    path = EXAMPLES / name
    return path.name, path.read_bytes()


def test_parse_bidder_csv_reads_items_and_amounts():
    bidder = parse_bidder_csv("Alpha", SMALL_CSV)
    assert bidder.name == "Alpha"
    assert len(bidder.items) == 2
    assert bidder.items[1].amount == 2000.0
    assert bidder.total == 7000.0


def test_totals_by_trade():
    bidder = parse_bidder_csv("Alpha", SMALL_CSV)
    assert bidder.totals_by_trade == {
        "Preliminaries": 5000.0,
        "Earthworks": 2000.0,
    }


def test_parse_missing_column_raises():
    with pytest.raises(ValueError, match="missing column"):
        parse_bidder_csv("Alpha", "item_no,description,trade,unit,quantity\nA1,X,Preliminaries,lot,1\n")


def test_parse_empty_file_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_bidder_csv("Alpha", "")


def test_parse_bad_number_raises():
    bad = SMALL_CSV.replace("100,20", "100,twenty")
    with pytest.raises(ValueError, match="not a number"):
        parse_bidder_csv("Alpha", bad)


def test_median_rate():
    assert median_rate([10, 20, 30]) == 20.0
    assert median_rate([10, 20]) == 15.0
    assert median_rate([]) is None


def test_compare_bidders_ranks_by_total():
    alpha = parse_bidder_csv("Alpha", SMALL_CSV)
    beta = parse_bidder_csv("Beta", SECOND_CSV)
    result = compare_bidders([beta, alpha])
    assert result.ranking == ["Alpha", "Beta"]
    assert result.bidders[0].total == 7000.0
    assert result.bidders[1].total == 8400.0
    assert result.spread_pct == pytest.approx(20.0)


def test_compare_needs_two_bidders():
    alpha = parse_bidder_csv("Alpha", SMALL_CSV)
    with pytest.raises(ValueError, match="at least two"):
        compare_bidders([alpha])


def test_outlier_flagged_when_rate_far_from_median():
    cheap = """item_no,description,trade,unit,quantity,rate
A1,Formwork,Formwork,m2,100,90
"""
    pricey = """item_no,description,trade,unit,quantity,rate
A1,Formwork,Formwork,m2,100,160
"""
    mid = """item_no,description,trade,unit,quantity,rate
A1,Formwork,Formwork,m2,100,95
"""
    result = compare_bidders(
        [
            parse_bidder_csv("Cheap", cheap),
            parse_bidder_csv("Pricey", pricey),
            parse_bidder_csv("Mid", mid),
        ]
    )
    assert len(result.outliers) == 1
    outlier = result.outliers[0]
    assert outlier.bidder == "Pricey"
    assert outlier.direction == "high"
    assert outlier.difference_pct == pytest.approx(68.4, abs=0.1)


def test_low_outlier_flagged_too():
    low = """item_no,description,trade,unit,quantity,rate
A1,Concrete,Concrete,m3,10,100
"""
    normal_a = """item_no,description,trade,unit,quantity,rate
A1,Concrete,Concrete,m3,10,200
"""
    normal_b = """item_no,description,trade,unit,quantity,rate
A1,Concrete,Concrete,m3,10,210
"""
    result = compare_bidders(
        [
            parse_bidder_csv("Low", low),
            parse_bidder_csv("Normal A", normal_a),
            parse_bidder_csv("Normal B", normal_b),
        ]
    )
    assert len(result.outliers) == 1
    assert result.outliers[0].bidder == "Low"
    assert result.outliers[0].direction == "low"


def test_rate_within_threshold_is_not_flagged():
    a = """item_no,description,trade,unit,quantity,rate
A1,Paint,Finishes,m2,100,12
"""
    b = """item_no,description,trade,unit,quantity,rate
A1,Paint,Finishes,m2,100,14
"""
    c = """item_no,description,trade,unit,quantity,rate
A1,Paint,Finishes,m2,100,11
"""
    result = compare_bidders(
        [
            parse_bidder_csv("A", a),
            parse_bidder_csv("B", b),
            parse_bidder_csv("C", c),
        ]
    )
    assert result.outliers == []


client = TestClient(app)


def test_home_page_serves_upload_form():
    response = client.get("/")
    assert response.status_code == 200
    assert "multipart/form-data" in response.text
    assert 'name="files"' in response.text


def test_json_endpoint_ranks_sample_bidders_and_flags_outliers():
    files = [
        ("files", load_example("alpha-builders.csv")),
        ("files", load_example("beta-construction.csv")),
        ("files", load_example("gamma-works.csv")),
    ]
    response = client.post("/api/compare", files=files)
    assert response.status_code == 200
    data = response.json()
    assert [row["name"] for row in data["ranking"]] == [
        "Gamma Works",
        "Alpha Builders",
        "Beta Construction",
    ]
    totals = {row["name"]: row["total"] for row in data["ranking"]}
    assert totals["Gamma Works"] == pytest.approx(209242.0)
    assert totals["Alpha Builders"] == pytest.approx(226230.0)
    assert totals["Beta Construction"] == pytest.approx(262036.0)
    assert data["spread_pct"] == pytest.approx(25.2, abs=0.1)
    flagged = {
        (outlier["item_no"], outlier["bidder"], outlier["direction"])
        for outlier in data["outliers"]
    }
    assert flagged == {
        ("D1", "Beta Construction", "high"),
        ("C1", "Gamma Works", "low"),
    }
    formwork = next(
        item for item in data["items"] if item["item_no"] == "D1"
    )
    assert formwork["median_rate"] == 95.0


def test_json_endpoint_accepts_bidder_names_form_field():
    files = [
        ("files", load_example("alpha-builders.csv")),
        ("files", load_example("beta-construction.csv")),
    ]
    response = client.post(
        "/api/compare",
        files=files,
        data={"bidder_names": "Team Red, Team Blue"},
    )
    assert response.status_code == 200
    assert [row["name"] for row in response.json()["ranking"]] == [
        "Team Red",
        "Team Blue",
    ]


def test_html_endpoint_returns_report():
    files = [
        ("files", load_example("alpha-builders.csv")),
        ("files", load_example("beta-construction.csv")),
        ("files", load_example("gamma-works.csv")),
    ]
    response = client.post("/compare", files=files)
    assert response.status_code == 200
    assert "Gamma Works" in response.text
    assert "Beta Construction" in response.text
    assert "Rates to look at" in response.text
    assert "Formwork to beams and columns" in response.text
    assert "outlier-high" in response.text
    assert "outlier-low" in response.text


def test_one_file_is_rejected():
    files = [("files", load_example("alpha-builders.csv"))]
    response = client.post("/api/compare", files=files)
    assert response.status_code == 400


def test_bad_csv_is_rejected():
    files = [
        ("files", ("a.csv", b"item_no,description\nA1,X\n")),
        ("files", ("b.csv", b"item_no,description\nA1,X\n")),
    ]
    response = client.post("/api/compare", files=files)
    assert response.status_code == 400
    assert "missing column" in response.json()["detail"]


def test_bidder_with_unpriced_item_still_compares():
    one = """item_no,description,trade,unit,quantity,rate
A1,Site establishment,Preliminaries,lot,1,5000
B1,Excavation,Earthworks,m3,100,20
"""
    two = """item_no,description,trade,unit,quantity,rate
A1,Site establishment,Preliminaries,lot,1,5500
"""
    result = compare_bidders(
        [parse_bidder_csv("One", one), parse_bidder_csv("Two", two)]
    )
    excavation = next(item for item in result.items if item.item_no == "B1")
    assert excavation.rates == {"One": 20.0}
    assert excavation.median == 20.0
    assert result.outliers == []
