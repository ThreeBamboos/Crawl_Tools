import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from crawl_tools.output import export_dataframe, fill_placeholders
from crawl_tools.schema import Step


class ActionError(Exception):
    pass


@dataclass
class Context:
    username: str
    password: str
    output_dir: str
    now: datetime
    last_table: pd.DataFrame | None = None


def _require(step: Step, field: str):
    val = getattr(step, field)
    if val is None:
        raise ActionError(f"action '{step.action}' requires '{field}'")
    return val


def navigate(page, step: Step, ctx: Context):
    page.goto(_require(step, "url"))


def click(page, step: Step, ctx: Context):
    page.click(_require(step, "selector"))


def wait_for(page, step: Step, ctx: Context):
    selector = _require(step, "selector")
    timeout = (step.timeout or 60) * 1000
    page.wait_for_selector(selector, timeout=timeout)


def fill(page, step: Step, ctx: Context):
    page.fill(_require(step, "selector"), _require(step, "value"))


def select_option(page, step: Step, ctx: Context):
    page.select_option(_require(step, "selector"), _require(step, "value"))


def login(page, step: Step, ctx: Context):
    page.fill(_require(step, "username_selector"), ctx.username)
    page.fill(_require(step, "password_selector"), ctx.password)
    page.click(_require(step, "submit_selector"))
    page.wait_for_selector(_require(step, "success_selector"), timeout=60000)


def manual(page, step: Step, ctx: Context):
    reason = step.reason or "Manual step: complete the action in the browser"
    print(f"\n[manual] {reason}")
    wf = step.wait_for
    if wf and wf.selector:
        timeout_s = wf.timeout or 180
        print(f"[manual] waiting up to {timeout_s}s for '{wf.selector}' ...")
        page.wait_for_selector(wf.selector, timeout=timeout_s * 1000)
    else:
        input("[manual] press Enter when ready to continue ... ")


def download(page, step: Step, ctx: Context):
    selector = _require(step, "selector")
    save_as = fill_placeholders(_require(step, "save_as"), ctx.now)
    target = Path(ctx.output_dir) / save_as
    target.parent.mkdir(parents=True, exist_ok=True)
    with page.expect_download(timeout=(step.timeout or 60) * 1000) as download_info:
        page.click(selector)
    download_info.value.save_as(str(target))


def extract_table(page, step: Step, ctx: Context):
    selector = _require(step, "selector")
    # inner_html() returns the matched element's children (no opening tag),
    # so for a table selector we get a bare <tbody> that pandas/lxml rejects.
    # Wrap in <table> so both real-browser fragments and full-table strings parse.
    html = f"<table>{page.inner_html(selector)}</table>"
    tables = pd.read_html(io.StringIO(html))
    if not tables:
        raise ActionError(f"No <table> found inside {selector!r}")
    ctx.last_table = tables[0]
    return tables[0]


def export(page, step: Step, ctx: Context):
    if ctx.last_table is None:
        raise ActionError("export requires a preceding extract_table")
    save_as = fill_placeholders(_require(step, "save_as"), ctx.now)
    export_dataframe(ctx.last_table, Path(ctx.output_dir) / save_as)


ACTION_REGISTRY = {
    "navigate": navigate,
    "click": click,
    "wait": wait_for,
    "fill": fill,
    "select": select_option,
    "login": login,
    "manual": manual,
    "download": download,
    "extract_table": extract_table,
    "export": export,
}


def dispatch(page, step: Step, ctx: Context):
    fn = ACTION_REGISTRY.get(step.action)
    if fn is None:
        raise ActionError(f"Unknown action: {step.action}")
    fn(page, step, ctx)
