from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from crawl_tools.output import fill_placeholders, export_dataframe


def test_fill_placeholders_date():
    now = datetime(2026, 6, 15, 9, 30, 5)
    assert fill_placeholders("sales-{date}.xlsx", now) == "sales-2026-06-15.xlsx"


def test_fill_placeholders_timestamp():
    now = datetime(2026, 6, 15, 9, 30, 5)
    assert fill_placeholders("r-{timestamp}.csv", now) == "r-20260615-093005.csv"


def test_export_dataframe_csv(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    target = tmp_path / "nested" / "out.csv"
    path = export_dataframe(df, target)
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("a,b")


def test_export_dataframe_xlsx(tmp_path):
    df = pd.DataFrame({"a": [1, 2]})
    target = tmp_path / "out.xlsx"
    export_dataframe(df, target)
    assert target.exists()
    assert target.stat().st_size > 0


def test_export_dataframe_unsupported_format(tmp_path):
    with pytest.raises(ValueError):
        export_dataframe(pd.DataFrame({"a": [1]}), tmp_path / "out.txt")
