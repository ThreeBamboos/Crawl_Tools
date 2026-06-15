from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def should_load_state(storage_state: str | Path, reuse: bool) -> str | None:
    if not reuse:
        return None
    p = Path(storage_state)
    return str(p) if p.exists() else None


def state_path_for(storage_state: str | Path) -> Path:
    return Path(storage_state)


@contextmanager
def open_browser(headless: bool, storage_state: str, reuse: bool = True):
    """打开 Playwright chromium,支持会话复用;退出时保存 storage_state。"""
    load_state = should_load_state(storage_state, reuse)
    state_p = state_path_for(storage_state)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=load_state)
        page: Page = context.new_page()
        try:
            yield page
            if reuse:
                state_p.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(state_p))
        finally:
            browser.close()
