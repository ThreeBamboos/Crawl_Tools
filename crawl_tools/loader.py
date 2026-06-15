from pathlib import Path

import yaml

from crawl_tools.schema import (
    FullJob, JobSpec, LoginConfig, Platform, Step,
)

PLATFORMS_DIR = Path("platforms")
JOBS_DIR = Path("jobs")


def resolve_platform_path(name: str, platforms_dir: Path = PLATFORMS_DIR) -> Path:
    candidate = Path(name)
    if candidate.is_file():
        return candidate
    for ext in (".yaml", ".yml"):
        by_name = platforms_dir / f"{name}{ext}"
        if by_name.is_file():
            return by_name
    available = (
        sorted(p.stem for p in platforms_dir.glob("*.y*ml"))
        if platforms_dir.is_dir() else []
    )
    raise FileNotFoundError(
        f"Platform '{name}' not found. Available: {', '.join(available) or '(none)'}"
    )


def load_platform(name: str, platforms_dir: Path = PLATFORMS_DIR) -> Platform:
    path = resolve_platform_path(name, platforms_dir)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Platform.model_validate(data)


def load_job_spec(path: Path | str) -> JobSpec:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return JobSpec.model_validate(data)


def _login_steps(login: LoginConfig) -> list[Step]:
    steps = [
        Step(action="navigate", url=login.url),
        Step(
            action="login",
            username_selector=login.username_selector,
            password_selector=login.password_selector,
            submit_selector=login.submit_selector,
            success_selector=login.success_selector,
        ),
    ]
    if login.captcha:
        steps.append(
            Step(
                action="manual",
                reason=login.captcha.manual.reason,
                wait_for=login.captcha.manual.wait_for,
            )
        )
    return steps


def merge_job(job: JobSpec, platform: Platform) -> FullJob:
    return FullJob(
        name=job.name,
        browser=platform.browser,
        session=platform.session,
        credentials=platform.credentials,
        start_url=platform.login.url,
        steps=_login_steps(platform.login) + job.steps,
        output=job.output,
    )


def job_from_dict(data: dict) -> FullJob:
    return FullJob.model_validate(data)


def load_and_merge(job_path: Path | str, platforms_dir: Path = PLATFORMS_DIR) -> FullJob:
    job = load_job_spec(job_path)
    platform = load_platform(job.platform, platforms_dir)
    return merge_job(job, platform)
