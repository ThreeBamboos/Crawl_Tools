import pathlib
from datetime import datetime

import pytest
from playwright.sync_api import sync_playwright

from crawl_tools.runtime.actions import Context, extract_table, navigate
from crawl_tools.schema import Step

FIXTURE = "file://" + str((pathlib.Path(__file__).parent / "fixtures" / "sample_site.html").resolve())


@pytest.mark.slow
def test_navigate_and_extract_table_from_local_html(tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()
        ctx = Context(username="u", password="p", output_dir=str(tmp_path), now=datetime.now())
        navigate(page, Step(action="navigate", url=FIXTURE), ctx)
        extract_table(page, Step(action="extract_table", selector="#t"), ctx)
        assert list(ctx.last_table["a"]) == [1]
        assert list(ctx.last_table["b"]) == [2]
        browser.close()
