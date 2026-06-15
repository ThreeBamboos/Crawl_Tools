from crawl_tools.runtime.browser import should_load_state, state_path_for


def test_should_load_state_false_when_file_missing(tmp_path):
    assert should_load_state(tmp_path / "missing.json", reuse=True) is None


def test_should_load_state_true_when_exists(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{}")
    assert should_load_state(p, reuse=True) == str(p)


def test_should_load_state_none_when_reuse_false(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{}")
    assert should_load_state(p, reuse=False) is None
