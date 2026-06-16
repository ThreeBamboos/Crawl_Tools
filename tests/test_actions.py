from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from crawl_tools.runtime.actions import (
    ActionError, Context, ACTION_REGISTRY, dispatch, navigate, click,
    download, extract_table, export,
)
from crawl_tools.schema import Step


class StubPage:
    """记录调用、提供 extract_table 所需 inner_html。"""
    def __init__(self, inner_html="<table></table>"):
        self.calls = []
        self._inner_html = inner_html

    def goto(self, url): self.calls.append(("goto", url))
    def click(self, sel): self.calls.append(("click", sel))
    def fill(self, sel, val): self.calls.append(("fill", sel, val))
    def select_option(self, sel, val): self.calls.append(("select", sel, val))
    def wait_for_selector(self, sel, timeout=None): self.calls.append(("wait", sel, timeout))
    def inner_html(self, sel):
        self.calls.append(("inner_html", sel))
        return self._inner_html

    class _Expect:
        def __init__(self, page): self.page = page
        def __enter__(self): self.page.calls.append(("expect_download",)); return self
        def __exit__(self, *a):
            self.page.calls.append(("download_saved",)); return False
        @property
        def value(self):
            class D:
                def __init__(self, page): self.page = page
                def save_as(self, path): self.page.calls.append(("save_as", path))
            return D(self.page)

    def expect_download(self, **kw): return self._Expect(self)


def _ctx(tmp_path):
    return Context(username="u", password="p", output_dir=str(tmp_path), now=datetime(2026, 6, 15))


def test_registry_covers_all_actions():
    expected = {"navigate", "login", "fill", "select", "click", "wait",
                "download", "extract_table", "export", "manual"}
    assert expected <= set(ACTION_REGISTRY)


def test_dispatch_calls_registered_function(tmp_path):
    page = StubPage()
    dispatch(page, Step(action="navigate", url="https://x.test"), _ctx(tmp_path))
    assert ("goto", "https://x.test") in page.calls


def test_dispatch_raises_on_missing_required_field(tmp_path):
    # schema 保证 action 合法;真实 ActionError 来源是缺必填字段(_require)
    with pytest.raises(ActionError):
        dispatch(StubPage(), Step(action="navigate"), _ctx(tmp_path))  # 缺 url


def test_navigate_requires_url(tmp_path):
    with pytest.raises(ActionError):
        navigate(StubPage(), Step(action="navigate"), _ctx(tmp_path))


def test_download_clicks_and_saves(tmp_path):
    page = StubPage()
    download(page, Step(action="download", selector="#btn", save_as="f-{date}.xlsx"), _ctx(tmp_path))
    assert ("click", "#btn") in page.calls
    saved = [c for c in page.calls if c[0] == "save_as"]
    assert saved and "f-2026-06-15.xlsx" in saved[0][1]


def test_extract_table_sets_last_table(tmp_path):
    html = "<table><tr><th>a</th></tr><tr><td>1</td></tr></table>"
    page = StubPage(inner_html=html)
    ctx = _ctx(tmp_path)
    extract_table(page, Step(action="extract_table", selector="table"), ctx)
    assert ctx.last_table is not None
    assert list(ctx.last_table["a"]) == [1]


def test_export_writes_file(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.last_table = pd.DataFrame({"a": [1, 2]})
    export(StubPage(), Step(action="export", save_as="out-{date}.csv"), ctx)
    assert (tmp_path / "out-2026-06-15.csv").exists()
