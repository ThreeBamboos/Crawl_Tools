import os
import re
from collections.abc import Iterable

from dotenv import load_dotenv

VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


class MissingCredentialError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("Missing credential env vars: " + ", ".join(missing))


def find_placeholders(value: str) -> list[str]:
    return VAR_PATTERN.findall(value)


def resolve_value(value: str) -> str:
    load_dotenv()

    def repl(match: re.Match) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise MissingCredentialError([name])
        return os.environ[name]

    return VAR_PATTERN.sub(repl, value)


def check_resolvable(values: Iterable[str]) -> None:
    load_dotenv()
    missing: list[str] = []
    for value in values:
        for name in find_placeholders(value):
            if name not in os.environ and name not in missing:
                missing.append(name)
    if missing:
        raise MissingCredentialError(missing)
