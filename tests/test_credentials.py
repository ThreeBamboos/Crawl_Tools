import pytest

from crawl_tools.credentials import (
    find_placeholders, resolve_value, check_resolvable, MissingCredentialError,
)


def test_find_placeholders_extracts_var_names():
    assert find_placeholders("${USER}") == ["USER"]
    assert find_placeholders("u-${A}-v-${B}") == ["A", "B"]
    assert find_placeholders("no vars here") == []


def test_resolve_value_from_env(monkeypatch):
    monkeypatch.setenv("MY_VAR", "secret")
    assert resolve_value("token-${MY_VAR}-end") == "token-secret-end"


def test_resolve_value_raises_when_missing(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    with pytest.raises(MissingCredentialError):
        resolve_value("${MISSING_VAR}")


def test_check_resolvable_collects_all_missing(monkeypatch):
    monkeypatch.delenv("A", raising=False)
    monkeypatch.delenv("B", raising=False)
    with pytest.raises(MissingCredentialError) as exc:
        check_resolvable(["${A}", "x-${B}", "plain"])
    assert set(exc.value.missing) == {"A", "B"}


def test_check_resolvable_passes_when_all_present(monkeypatch):
    monkeypatch.setenv("A", "1")
    monkeypatch.setenv("B", "2")
    check_resolvable(["${A}", "${B}"])  # 不抛异常即通过
