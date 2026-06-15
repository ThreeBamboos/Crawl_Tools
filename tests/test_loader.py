from pathlib import Path

import pytest

from crawl_tools.loader import (
    load_platform, load_job_spec, merge_job, load_and_merge,
    job_from_dict, resolve_platform_path,
)
from crawl_tools.schema import FullJob

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_platform():
    p = load_platform("erp-a", platforms_dir=FIXTURES)
    assert p.name == "erp-a"
    assert p.login.url == "https://erp-a.test/login"
    assert p.login.captcha.manual.wait_for.timeout == 180


def test_resolve_platform_path_missing_lists_available():
    with pytest.raises(FileNotFoundError) as exc:
        resolve_platform_path("nope", platforms_dir=FIXTURES)
    assert "erp-a" in str(exc.value)


def test_load_job_spec():
    j = load_job_spec(FIXTURES / "job.yaml")
    assert j.name == "erp-a-sales"
    assert j.platform == "erp-a"
    assert len(j.steps) == 3


def test_merge_prepends_login_and_captcha_steps():
    j = load_job_spec(FIXTURES / "job.yaml")
    p = load_platform("erp-a", platforms_dir=FIXTURES)
    full = merge_job(j, p)
    assert isinstance(full, FullJob)
    # navigate(login url) + login + manual(captcha) + 3 job steps = 6
    actions = [s.action for s in full.steps]
    assert actions == ["navigate", "login", "manual", "navigate", "wait", "download"]
    assert full.start_url == "https://erp-a.test/login"
    assert full.credentials.username == "${ERP_A_USER}"


def test_load_and_merge_end_to_end():
    full = load_and_merge(FIXTURES / "job.yaml", platforms_dir=FIXTURES)
    assert full.name == "erp-a-sales"
    assert full.browser.headless is False


def test_job_from_dict_roundtrip():
    full = load_and_merge(FIXTURES / "job.yaml", platforms_dir=FIXTURES)
    rebuilt = job_from_dict(full.model_dump(mode="json"))
    assert [s.action for s in rebuilt.steps] == [s.action for s in full.steps]
