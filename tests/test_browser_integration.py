import pytest


@pytest.mark.slow
def test_open_browser_lifecycle(tmp_path):
    from crawl_tools.runtime.browser import open_browser

    state = tmp_path / "session.json"
    with open_browser(headless=True, storage_state=str(state), reuse=True) as page:
        assert page is not None
    # 退出后应保存会话文件
    assert state.exists()
