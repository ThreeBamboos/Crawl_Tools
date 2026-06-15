from datetime import datetime
from pathlib import Path

import pandas as pd

PLACEHOLDER_DATE = "%Y-%m-%d"
PLACEHOLDER_TIMESTAMP = "%Y%m%d-%H%M%S"


def fill_placeholders(filename: str, now: datetime) -> str:
    return filename.format(
        date=now.strftime(PLACEHOLDER_DATE),
        timestamp=now.strftime(PLACEHOLDER_TIMESTAMP),
    )


def export_dataframe(df: pd.DataFrame, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = target.suffix.lower()
    if suffix == ".csv":
        df.to_csv(target, index=False)
    elif suffix in (".xlsx", ".xls"):
        df.to_excel(target, index=False)
    else:
        raise ValueError(f"Unsupported export format: {suffix!r}")
    return target
