import pytest
from pydantic import ValidationError

from crawl_tools.schema import (
    BrowserConfig, SessionConfig, WaitFor, ManualConfig, CaptchaConfig,
    LoginConfig, Credentials, Platform, Step, OutputConfig, JobSpec, FullJob,
)


def test_browser_config_defaults_headless_false():
    assert BrowserConfig().headless is False


def test_session_config_requires_storage_state():
    with pytest.raises(ValidationError):
        SessionConfig()  # storage_state 必填


def test_step_action_must_be_known():
    with pytest.raises(ValidationError):
        Step(action="explode")


def test_step_optional_fields_default_none():
    s = Step(action="navigate", url="https://x.test")
    assert s.action == "navigate"
    assert s.url == "https://x.test"
    assert s.selector is None


def test_login_config_with_optional_captcha():
    login = LoginConfig(
        url="https://x.test/login",
        username_selector="#u", password_selector="#p",
        submit_selector="#s", success_selector=".ok",
    )
    assert login.captcha is None


def test_platform_validates_full_structure():
    p = Platform(
        name="erp-a",
        login={"url": "https://x.test/login", "username_selector": "#u",
               "password_selector": "#p", "submit_selector": "#s",
               "success_selector": ".ok"},
        credentials={"username": "${ERP_A_USER}", "password": "${ERP_A_PASSWORD}"},
        session={"storage_state": "./.session/erp-a.json"},
    )
    assert p.browser.headless is False
    assert p.session.reuse is True
    assert p.credentials.username == "${ERP_A_USER}"


def test_jobspec_minimal():
    j = JobSpec(name="sales", platform="erp-a", steps=[{"action": "navigate", "url": "https://x.test"}])
    assert j.output.dir == "./downloads"
    assert j.steps[0].action == "navigate"


def test_fulljob_requires_merged_fields():
    with pytest.raises(ValidationError):
        FullJob(name="x")  # 缺 browser/session/credentials/start_url/steps
