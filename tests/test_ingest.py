import pytest

from app.engine.ingest import IngestError, parse_sales_csv

GOOD = ("sku,date,units_sold,stockout,name,unit_cost,unit_price\n"
        "A,2026-06-01,10,0,Cola,0.6,1.5\n"
        "A,2026-06-02,3,1,,,\n"
        "B,2026-06-01,5,false,,,\n")


def test_parses_batches_with_attrs_and_flags():
    batches = {b.sku_key: b for b in parse_sales_csv(GOOD)}
    assert set(batches) == {"A", "B"}
    a = batches["A"]
    assert a.name == "Cola" and a.unit_cost == 0.6 and a.unit_price == 1.5
    assert [s.stockout for s in a.sales] == [False, True]
    assert batches["B"].unit_cost is None


@pytest.mark.parametrize("text,fragment", [
    ("", "empty CSV"),
    ("sku,date\nA,2026-06-01\n", "missing required columns"),
    ("sku,date,units_sold,stockout\nA,junk,5,0\n", "bad date"),
    ("sku,date,units_sold,stockout\nA,2026-06-01,x,0\n", "bad units_sold"),
    ("sku,date,units_sold,stockout\nA,2026-06-01,-2,0\n", "negative"),
    ("sku,date,units_sold,stockout\nA,2026-06-01,5,maybe\n", "bad stockout"),
    ("sku,date,units_sold,stockout\nA,2026-06-01,5,\n", "bad stockout"),      # blank cell
    ("sku,date,units_sold,stockout\nA,2026-06-01,5\n", "bad stockout"),       # truncated row
    ("sku,date,units_sold,stockout\nA,2026-06-01,5,0\nA,2026-06-01,6,0\n", "duplicate"),
    ("sku,date,units_sold,stockout\n", "no data rows"),
])
def test_rejects_bad_input_with_reason(text, fragment):
    with pytest.raises(IngestError, match=fragment):
        parse_sales_csv(text)
