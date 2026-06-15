from datetime import datetime
from pathlib import Path

from crawl_tools.credentials import MissingCredentialError, check_resolvable, resolve_value
from crawl_tools.runtime.actions import Context, dispatch
from crawl_tools.runtime.browser import open_browser
from crawl_tools.schema import Credentials, FullJob

LOGS_DIR = Path("logs")


class JobError(Exception):
    pass


def _resolve_creds(creds: Credentials) -> tuple[str, str]:
    try:
        check_resolvable([creds.username, creds.password])
    except MissingCredentialError:
        raise
    return resolve_value(creds.username), resolve_value(creds.password)


def screenshot(page, job_name: str, step_index: int, logs_dir: Path = LOGS_DIR) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"{job_name}_{step_index}.png"
    try:
        page.screenshot(path=str(path))
    except Exception:
        pass
    return path


def run_job(job: FullJob, *, now: datetime | None = None) -> None:
    if now is None:
        now = datetime.now()
    username, password = _resolve_creds(job.credentials)
    ctx = Context(
        username=username, password=password,
        output_dir=job.output.dir, now=now,
    )
    Path(job.output.dir).mkdir(parents=True, exist_ok=True)
    with open_browser(
        job.browser.headless, job.session.storage_state, job.session.reuse
    ) as page:
        for i, step in enumerate(job.steps):
            try:
                dispatch(page, step, ctx)
            except Exception as e:
                screenshot(page, job.name, i)
                raise JobError(f"Step {i} ({step.action}) failed: {e}") from e
