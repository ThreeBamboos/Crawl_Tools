from datetime import datetime
from pathlib import Path

import pytest

from crawl_tools.runtime import executor
from crawl_tools.runtime.executor import JobError, run_job, screenshot
from crawl_tools.schema import (
    BrowserConfig, Credentials, FullJob, OutputConfig, SessionConfig, Step,
)


class RecordingPage:
    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on

    def goto(self, url): self._maybe("goto")
    def click(self, sel): self._maybe("click")
    def fill(self, sel, val): self._maybe("fill")
    def wait_for_selector(self, sel, timeout=None): self._maybe("wait")
    def screenshot(self, path): self.calls.append(("screenshot", path))

    def _maybe(self, name):
        self.calls.append((name,))
        if self._fail_on == name:
            raise RuntimeError(f"boom at {name}")


class _Ctx:
    def __enter__(self): return None
    def __exit__(self, *a): return False


def _ctxmgr(page):
    class Mgr:
        def __enter__(self): return page
        def __exit__(self, *a): return False
    return Mgr()


def _make_job(steps):
    return FullJob(
        name="t", browser=BrowserConfig(headless=True),
        session=SessionConfig(storage_state="./.session/t.json", reuse=False),
        credentials=Credentials(username="u", password="p"),
        start_url="https://x.test/login",
        steps=steps, output=OutputConfig(dir="./downloads"),
    )


def test_run_job_dispatches_all_steps(monkeypatch):
    page = RecordingPage()
    monkeypatch.setattr(executor, "open_browser", lambda *a, **kw: _ctxmgr(page))
    monkeypatch.setenv("U", "u"); monkeypatch.setenv("P", "p")
    job = _make_job([
        Step(action="navigate", url="https://x.test"),
        Step(action="click", selector="#a"),
    ])
    job = job.model_copy(update={"credentials": Credentials(username="${U}", password="${P}")})
    run_job(job, now=datetime(2026, 6, 15))
    names = [c[0] for c in page.calls]
    assert "goto" in names and "click" in names


def test_run_job_screenshot_on_error(monkeypatch, tmp_path):
    page = RecordingPage(fail_on="click")
    monkeypatch.setattr(executor, "open_browser", lambda *a, **kw: _ctxmgr(page))
    monkeypatch.setattr(executor, "screenshot", lambda p, n, i, d=tmp_path: d / f"{n}_{i}.png")
    job = _make_job([Step(action="click", selector="#a")])
    with pytest.raises(JobError) as exc:
        run_job(job, now=datetime(2026, 6, 15))
    assert "Step 0" in str(exc.value)


def test_run_job_missing_credential_raises(monkeypatch):
    monkeypatch.delenv("NOPE_U", raising=False)
    monkeypatch.setattr(executor, "open_browser", lambda *a, **kw: _ctxmgr(RecordingPage()))
    job = _make_job([Step(action="navigate", url="https://x.test")])
    job = job.model_copy(update={"credentials": Credentials(username="${NOPE_U}", password="p")})
    with pytest.raises(Exception):
        run_job(job, now=datetime(2026, 6, 15))
