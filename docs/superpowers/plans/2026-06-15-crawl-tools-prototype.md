# Crawl_Tools 原型实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个 YAML 驱动的爬虫原型：平台/任务 YAML → 编译成可读的薄 Python 脚本（调用动作库）→ 直接执行或导出，自动登录目标站并下载/抓取数据表。

**Architecture:** 五层单向数据流 —— ① loader 加载并合并 platform+job YAML → FullJob 模型；② codegen 把 FullJob 编译成薄 .py（嵌入 job 数据 + 调用 run_job）；③ executor 解析凭据并运行；④ actions 动作库通过 Playwright 执行 login/navigate/click/wait/download/extract_table/export/manual；⑤ 输出到 downloads/。YAML 是唯一真相源，编译器与动作库解耦，为后期 AI 解析层留接口。

**Tech Stack:** Python 3.10+ · Playwright（浏览器自动化）· pydantic v2（schema 校验）· PyYAML · pandas + openpyxl（表格导出）· typer（CLI）· python-dotenv（凭据）· pytest（TDD）

**Spec:** `docs/superpowers/specs/2026-06-14-crawl-tools-design.md`

---

## 文件结构与职责

| 文件 | 职责 |
|---|---|
| `pyproject.toml` | 包定义、依赖、`crawl` 命令入口、pytest 配置 |
| `crawl_tools/__init__.py` | 包标识 |
| `crawl_tools/schema.py` | pydantic 模型：`Platform`/`JobSpec`/`FullJob`/`Step`/配置类 |
| `crawl_tools/credentials.py` | `${VAR}` 占位符发现与解析（env / .env），缺失即报错 |
| `crawl_tools/output.py` | 文件名占位符 `{date}`/`{timestamp}` + DataFrame 导出 xlsx/csv |
| `crawl_tools/loader.py` | 加载 platform/job YAML、合并为 `FullJob`、`job_from_dict` |
| `crawl_tools/compiler/__init__.py` | 子包标识 |
| `crawl_tools/compiler/codegen.py` | `FullJob` → 薄 `.py` 脚本 |
| `crawl_tools/runtime/__init__.py` | 子包标识 |
| `crawl_tools/runtime/browser.py` | Playwright 浏览器 + 会话 storage_state 封装 |
| `crawl_tools/runtime/actions.py` | 动作库（10 个动作）+ `dispatch` + `Context` |
| `crawl_tools/runtime/executor.py` | `run_job`：解析凭据、逐步执行、出错截图 |
| `crawl_tools/cli.py` | typer 入口：`list`/`run`/`build`/`dry-run`/`init` |
| `platforms/*.yaml`、`jobs/*.yaml` | 平台与任务定义（用户编写） |
| `tests/` | 单测（schema/credentials/output/loader/codegen/actions/executor/cli） |

**实现说明（对 spec 一处细化）**：spec 示例把"点导出按钮"写成 `click` + `download` 两步。但 Playwright 要求 `expect_download()` 必须包裹触发动作本身，两步分离无法可靠截获。因此实现中 **`download` 动作自包含**：它接收 `selector`（要点的按钮）+ `save_as`，内部"设置下载监听 → 点击 → 保存"。普通点击仍用独立 `click` 动作。这是 Playwright 正确性所需的最小细化。

---

## Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `crawl_tools/__init__.py`
- Create: `crawl_tools/compiler/__init__.py`
- Create: `crawl_tools/runtime/__init__.py`
- Create: `tests/__init__.py`
- Create: `.env.example`
- Modify: `.gitignore`（追加 generated/ downloads/ .session/ .env logs/）

- [ ] **Step 1: 写 `pyproject.toml`**

```toml
[project]
name = "crawl-tools"
version = "0.1.0"
description = "YAML-driven web crawler: process description -> Playwright code -> data download"
requires-python = ">=3.10"
dependencies = [
    "playwright>=1.40",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "pandas>=2.0",
    "openpyxl>=3.1",
    "typer>=0.9",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[project.scripts]
crawl = "crawl_tools.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["crawl_tools"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["slow: integration tests requiring a real browser"]
addopts = "-m 'not slow'"
```

- [ ] **Step 2: 写空 `__init__.py` 文件**

`crawl_tools/__init__.py`、`crawl_tools/compiler/__init__.py`、`crawl_tools/runtime/__init__.py`、`tests/__init__.py` 内容均为空字符串（占位包标识）。

- [ ] **Step 3: 写 `.env.example`**

```
# 每个平台一组凭据;复制为 .env 并填入真实值(.env 已 gitignore)
ERP_A_USER=
ERP_A_PASSWORD=
```

- [ ] **Step 4: 追加 `.gitignore`**

在 `.gitignore` 末尾追加：

```
# Crawl_Tools 运行产物
generated/
downloads/
.session/
logs/
.env
```

- [ ] **Step 5: 安装包与 Playwright 内核**

Run:
```bash
pip install -e ".[dev]"
playwright install chromium
```
Expected: 安装成功，无错误。

- [ ] **Step 6: 烟雾测试（应失败：cli 尚未实现）**

Run: `crawl --help`
Expected: 报错或无输出（cli.py 还没写）。本步只确认入口已注册；真正的验证在 Task 10。

- [ ] **Step 7: 提交**

```bash
git add pyproject.toml crawl_tools/ tests/__init__.py .env.example .gitignore
git commit -m "chore: scaffold crawl_tools package and project config"
```

---

## Task 2: Schema 模型（`schema.py`）

**Files:**
- Create: `crawl_tools/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: 写失败测试 `tests/test_schema.py`**

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_schema.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'crawl_tools.schema'`

- [ ] **Step 3: 写实现 `crawl_tools/schema.py`**

```python
from typing import Literal, Optional

from pydantic import BaseModel, Field

ActionType = Literal[
    "navigate", "login", "fill", "select", "click", "wait",
    "download", "extract_table", "export", "manual",
]


class BrowserConfig(BaseModel):
    headless: bool = False


class SessionConfig(BaseModel):
    storage_state: str
    reuse: bool = True


class WaitFor(BaseModel):
    selector: Optional[str] = None
    timeout: int = 60


class ManualConfig(BaseModel):
    reason: Optional[str] = None
    wait_for: WaitFor = Field(default_factory=WaitFor)


class CaptchaConfig(BaseModel):
    manual: ManualConfig


class LoginConfig(BaseModel):
    url: str
    username_selector: str
    password_selector: str
    submit_selector: str
    success_selector: str
    captcha: Optional[CaptchaConfig] = None


class Credentials(BaseModel):
    username: str
    password: str


class Platform(BaseModel):
    name: str
    login: LoginConfig
    credentials: Credentials
    session: SessionConfig
    browser: BrowserConfig = Field(default_factory=BrowserConfig)


class Step(BaseModel):
    action: ActionType
    url: Optional[str] = None
    selector: Optional[str] = None
    value: Optional[str] = None
    timeout: Optional[int] = None
    save_as: Optional[str] = None
    format: Optional[str] = None
    username_selector: Optional[str] = None
    password_selector: Optional[str] = None
    submit_selector: Optional[str] = None
    success_selector: Optional[str] = None
    reason: Optional[str] = None
    wait_for: Optional[WaitFor] = None


class OutputConfig(BaseModel):
    dir: str = "./downloads"


class JobSpec(BaseModel):
    """任务文件(用户编写),按名字引用平台。"""
    name: str
    platform: str
    steps: list[Step]
    output: OutputConfig = Field(default_factory=OutputConfig)


class FullJob(BaseModel):
    """合并平台后的完整任务,自包含可执行。"""
    name: str
    browser: BrowserConfig
    session: SessionConfig
    credentials: Credentials
    start_url: str
    steps: list[Step]
    output: OutputConfig
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_schema.py -v`
Expected: 8 passed

- [ ] **Step 5: 提交**

```bash
git add crawl_tools/schema.py tests/test_schema.py
git commit -m "feat(schema): pydantic models for platform/job/step/config"
```

---

## Task 3: 凭据解析（`credentials.py`）

**Files:**
- Create: `crawl_tools/credentials.py`
- Test: `tests/test_credentials.py`

- [ ] **Step 1: 写失败测试 `tests/test_credentials.py`**

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_credentials.py -v`
Expected: FAIL —— `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `crawl_tools/credentials.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_credentials.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add crawl_tools/credentials.py tests/test_credentials.py
git commit -m "feat(credentials): resolve \${VAR} placeholders from env/.env"
```

---

## Task 4: 输出辅助（`output.py`）

**Files:**
- Create: `crawl_tools/output.py`
- Test: `tests/test_output.py`

- [ ] **Step 1: 写失败测试 `tests/test_output.py`**

```python
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from crawl_tools.output import fill_placeholders, export_dataframe


def test_fill_placeholders_date():
    now = datetime(2026, 6, 15, 9, 30, 5)
    assert fill_placeholders("sales-{date}.xlsx", now) == "sales-2026-06-15.xlsx"


def test_fill_placeholders_timestamp():
    now = datetime(2026, 6, 15, 9, 30, 5)
    assert fill_placeholders("r-{timestamp}.csv", now) == "r-20260615-093005.csv"


def test_export_dataframe_csv(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    target = tmp_path / "nested" / "out.csv"
    path = export_dataframe(df, target)
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("a,b")


def test_export_dataframe_xlsx(tmp_path):
    df = pd.DataFrame({"a": [1, 2]})
    target = tmp_path / "out.xlsx"
    export_dataframe(df, target)
    assert target.exists()
    assert target.stat().st_size > 0


def test_export_dataframe_unsupported_format(tmp_path):
    with pytest.raises(ValueError):
        export_dataframe(pd.DataFrame({"a": [1]}), tmp_path / "out.txt")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_output.py -v`
Expected: FAIL —— `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `crawl_tools/output.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_output.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add crawl_tools/output.py tests/test_output.py
git commit -m "feat(output): filename placeholders and dataframe export"
```

---

## Task 5: 加载与合并（`loader.py`）

**Files:**
- Create: `crawl_tools/loader.py`
- Test: `tests/test_loader.py`
- Create fixtures: `tests/fixtures/platform.yaml`, `tests/fixtures/job.yaml`

- [ ] **Step 1: 写 fixture `tests/fixtures/erp-a.yaml`**（文件名=平台名,loader 按名查找）

```yaml
name: erp-a
login:
  url: https://erp-a.test/login
  username_selector: "input[name='username']"
  password_selector: "input[name='password']"
  submit_selector: "button[type='submit']"
  success_selector: "a.logout"
  captcha:
    manual:
      reason: "若出现验证码请手动完成"
      wait_for:
        selector: "a.logout"
        timeout: 180
credentials:
  username: ${ERP_A_USER}
  password: ${ERP_A_PASSWORD}
session:
  storage_state: ./.session/erp-a.json
  reuse: true
browser:
  headless: false
```

- [ ] **Step 2: 写 fixture `tests/fixtures/job.yaml`**

```yaml
name: erp-a-sales
platform: erp-a
steps:
  - action: navigate
    url: https://erp-a.test/reports/sales
  - action: wait
    selector: "table.report-table"
  - action: download
    selector: "button.export-excel"
    save_as: erp-a-sales-{date}.xlsx
output:
  dir: ./downloads
```

- [ ] **Step 3: 写失败测试 `tests/test_loader.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认失败**

Run: `pytest tests/test_loader.py -v`
Expected: FAIL —— `ModuleNotFoundError`

- [ ] **Step 5: 写实现 `crawl_tools/loader.py`**

```python
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
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `pytest tests/test_loader.py -v`
Expected: 6 passed

- [ ] **Step 7: 提交**

```bash
git add crawl_tools/loader.py tests/test_loader.py tests/fixtures/
git commit -m "feat(loader): load and merge platform+job YAML into FullJob"
```

---

## Task 6: 代码生成（`compiler/codegen.py`）

**Files:**
- Create: `crawl_tools/compiler/codegen.py`
- Test: `tests/test_codegen.py`

- [ ] **Step 1: 写失败测试 `tests/test_codegen.py`**

```python
from pathlib import Path

from crawl_tools.compiler.codegen import generate_script, write_script
from crawl_tools.loader import load_and_merge

FIXTURES = Path(__file__).parent / "fixtures"


def _job():
    return load_and_merge(FIXTURES / "job.yaml", platforms_dir=FIXTURES)


def test_generate_script_contains_header_and_job_name():
    src = generate_script(_job())
    assert "Auto-generated by Crawl_Tools" in src
    assert "erp-a-sales" in src
    assert "run_job" in src
    assert "job_from_dict" in src


def test_generated_script_is_valid_python():
    src = generate_script(_job())
    compile(src, "<generated>", "exec")  # 语法合法即不抛异常


def test_generated_script_embeds_steps():
    src = generate_script(_job())
    assert '"action": "login"' in src
    assert '"action": "download"' in src
    assert "${ERP_A_USER}" in src  # 占位符保留,运行时解析(不泄明文)


def test_write_script_creates_file(tmp_path):
    path = write_script(_job(), dest_dir=tmp_path)
    assert path.name == "erp-a-sales.py"
    assert path.exists()
    assert "run_job" in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_codegen.py -v`
Expected: FAIL —— `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `crawl_tools/compiler/codegen.py`**

```python
import json
from pathlib import Path

from crawl_tools.schema import FullJob

HEADER = '"""Auto-generated by Crawl_Tools. Edit with care."""'

TEMPLATE = '''{header}
# Job: {name}  (run: python {{this file}})
from crawl_tools.loader import job_from_dict
from crawl_tools.runtime.executor import run_job

JOB = {job_dict}

if __name__ == "__main__":
    run_job(job_from_dict(JOB))
'''


def generate_script(job: FullJob) -> str:
    job_dict = json.dumps(job.model_dump(mode="json"), indent=2, ensure_ascii=False)
    return TEMPLATE.format(header=HEADER, name=job.name, job_dict=job_dict)


def write_script(job: FullJob, dest_dir: Path | str = "generated") -> Path:
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{job.name}.py"
    path.write_text(generate_script(job), encoding="utf-8")
    return path
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_codegen.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add crawl_tools/compiler/codegen.py tests/test_codegen.py
git commit -m "feat(codegen): compile FullJob into a thin runnable script"
```

---

## Task 7: 浏览器封装（`runtime/browser.py`）

**Files:**
- Create: `crawl_tools/runtime/browser.py`
- Test: `tests/test_browser.py`（纯逻辑）+ `tests/test_browser_integration.py`（slow）

- [ ] **Step 1: 写失败测试 `tests/test_browser.py`**

```python
from pathlib import Path

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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_browser.py -v`
Expected: FAIL —— `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `crawl_tools/runtime/browser.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_browser.py -v`
Expected: 3 passed

- [ ] **Step 5: 写 slow 集成测试 `tests/test_browser_integration.py`**

```python
import pytest


@pytest.mark.slow
def test_open_browser_lifecycle(tmp_path):
    from crawl_tools.runtime.browser import open_browser

    state = tmp_path / "session.json"
    with open_browser(headless=True, storage_state=str(state), reuse=True) as page:
        assert page is not None
    # 退出后应保存会话文件
    assert state.exists()
```

- [ ] **Step 6: 提交**

```bash
git add crawl_tools/runtime/browser.py tests/test_browser.py tests/test_browser_integration.py
git commit -m "feat(runtime): playwright browser + session storage_state wrapper"
```

---

## Task 8: 动作库（`runtime/actions.py`）

**Files:**
- Create: `crawl_tools/runtime/actions.py`
- Test: `tests/test_actions.py`（用 stub page 测 dispatch 与参数校验）

- [ ] **Step 1: 写失败测试 `tests/test_actions.py`**

```python
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from crawl_tools.runtime.actions import (
    ActionError, Context, ACTION_REGISTRY, dispatch, navigate, click,
    download, extract_table, export,
)
from crawl_tools.schema import Step


class StubPage:
    """记录调用、提供 extract_table 所需 inner_html。"""
    def __init__(self, inner_html="<table></table>"):
        self.calls = []
        self._inner_html = inner_html

    def goto(self, url): self.calls.append(("goto", url))
    def click(self, sel): self.calls.append(("click", sel))
    def fill(self, sel, val): self.calls.append(("fill", sel, val))
    def select_option(self, sel, val): self.calls.append(("select", sel, val))
    def wait_for_selector(self, sel, timeout=None): self.calls.append(("wait", sel, timeout))
    def inner_html(self, sel):
        self.calls.append(("inner_html", sel))
        return self._inner_html

    class _Expect:
        def __init__(self, page): self.page = page
        def __enter__(self): self.page.calls.append(("expect_download",)); return self
        def __exit__(self, *a):
            self.page.calls.append(("download_saved",)); return False
        @property
        def value(self):
            class D:
                def __init__(self, page): self.page = page
                def save_as(self, path): self.page.calls.append(("save_as", path))
            return D(self.page)

    def expect_download(self): return self._Expect(self)


def _ctx(tmp_path):
    return Context(username="u", password="p", output_dir=str(tmp_path), now=datetime(2026, 6, 15))


def test_registry_covers_all_actions():
    expected = {"navigate", "login", "fill", "select", "click", "wait",
                "download", "extract_table", "export", "manual"}
    assert expected <= set(ACTION_REGISTRY)


def test_dispatch_calls_registered_function(tmp_path):
    page = StubPage()
    dispatch(page, Step(action="navigate", url="https://x.test"), _ctx(tmp_path))
    assert ("goto", "https://x.test") in page.calls


def test_dispatch_raises_on_missing_required_field(tmp_path):
    # schema 保证 action 合法;真实 ActionError 来源是缺必填字段(_require)
    with pytest.raises(ActionError):
        dispatch(StubPage(), Step(action="navigate"), _ctx(tmp_path))  # 缺 url


def test_navigate_requires_url(tmp_path):
    with pytest.raises(ActionError):
        navigate(StubPage(), Step(action="navigate"), _ctx(tmp_path))


def test_download_clicks_and_saves(tmp_path):
    page = StubPage()
    download(page, Step(action="download", selector="#btn", save_as="f-{date}.xlsx"), _ctx(tmp_path))
    assert ("click", "#btn") in page.calls
    saved = [c for c in page.calls if c[0] == "save_as"]
    assert saved and "f-2026-06-15.xlsx" in saved[0][1]


def test_extract_table_sets_last_table(tmp_path):
    html = "<table><tr><th>a</th></tr><tr><td>1</td></tr></table>"
    page = StubPage(inner_html=html)
    ctx = _ctx(tmp_path)
    extract_table(page, Step(action="extract_table", selector="table"), ctx)
    assert ctx.last_table is not None
    assert list(ctx.last_table["a"]) == [1]


def test_export_writes_file(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.last_table = pd.DataFrame({"a": [1, 2]})
    export(StubPage(), Step(action="export", save_as="out-{date}.csv"), ctx)
    assert (tmp_path / "out-2026-06-15.csv").exists()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_actions.py -v`
Expected: FAIL —— `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `crawl_tools/runtime/actions.py`**

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from crawl_tools.output import export_dataframe, fill_placeholders
from crawl_tools.schema import Step


class ActionError(Exception):
    pass


@dataclass
class Context:
    username: str
    password: str
    output_dir: str
    now: datetime
    last_table: pd.DataFrame | None = None


def _require(step: Step, field: str):
    val = getattr(step, field)
    if val is None:
        raise ActionError(f"action '{step.action}' requires '{field}'")
    return val


def navigate(page, step: Step, ctx: Context):
    page.goto(_require(step, "url"))


def click(page, step: Step, ctx: Context):
    page.click(_require(step, "selector"))


def wait_for(page, step: Step, ctx: Context):
    selector = _require(step, "selector")
    timeout = (step.timeout or 60) * 1000
    page.wait_for_selector(selector, timeout=timeout)


def fill(page, step: Step, ctx: Context):
    page.fill(_require(step, "selector"), _require(step, "value"))


def select_option(page, step: Step, ctx: Context):
    page.select_option(_require(step, "selector"), _require(step, "value"))


def login(page, step: Step, ctx: Context):
    page.fill(_require(step, "username_selector"), ctx.username)
    page.fill(_require(step, "password_selector"), ctx.password)
    page.click(_require(step, "submit_selector"))
    page.wait_for_selector(_require(step, "success_selector"), timeout=60000)


def manual(page, step: Step, ctx: Context):
    reason = step.reason or "Manual step: complete the action in the browser"
    print(f"\n[manual] {reason}")
    wf = step.wait_for
    if wf and wf.selector:
        timeout_s = wf.timeout or 180
        print(f"[manual] waiting up to {timeout_s}s for '{wf.selector}' ...")
        page.wait_for_selector(wf.selector, timeout=timeout_s * 1000)
    else:
        input("[manual] press Enter when ready to continue ... ")


def download(page, step: Step, ctx: Context):
    selector = _require(step, "selector")
    save_as = fill_placeholders(_require(step, "save_as"), ctx.now)
    target = Path(ctx.output_dir) / save_as
    target.parent.mkdir(parents=True, exist_ok=True)
    with page.expect_download() as download_info:
        page.click(selector)
    download_info.value.save_as(str(target))


def extract_table(page, step: Step, ctx: Context):
    selector = _require(step, "selector")
    html = page.inner_html(selector)
    tables = pd.read_html(html)
    if not tables:
        raise ActionError(f"No <table> found inside {selector!r}")
    ctx.last_table = tables[0]
    return tables[0]


def export(page, step: Step, ctx: Context):
    if ctx.last_table is None:
        raise ActionError("export requires a preceding extract_table")
    save_as = fill_placeholders(_require(step, "save_as"), ctx.now)
    export_dataframe(ctx.last_table, Path(ctx.output_dir) / save_as)


ACTION_REGISTRY = {
    "navigate": navigate,
    "click": click,
    "wait": wait_for,
    "fill": fill,
    "select": select_option,
    "login": login,
    "manual": manual,
    "download": download,
    "extract_table": extract_table,
    "export": export,
}


def dispatch(page, step: Step, ctx: Context):
    fn = ACTION_REGISTRY.get(step.action)
    if fn is None:
        raise ActionError(f"Unknown action: {step.action}")
    fn(page, step, ctx)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_actions.py -v`
Expected: 8 passed

- [ ] **Step 5: 提交**

```bash
git add crawl_tools/runtime/actions.py tests/test_actions.py
git commit -m "feat(actions): action library with dispatch and stub-page tests"
```

---

## Task 9: 执行器（`runtime/executor.py`）

**Files:**
- Create: `crawl_tools/runtime/executor.py`
- Test: `tests/test_executor.py`（stub page + monkeypatch open_browser 与截图）

- [ ] **Step 1: 写失败测试 `tests/test_executor.py`**

```python
from datetime import datetime
from pathlib import Path

import pytest

from crawl_tools.runtime import executor
from crawl_tools.runtime.executor import JobError, run_job, screenshot
from crawl_tools.schema import (
    BrowserConfig, Credentials, FullJob, OutputConfig, SessionConfig, Step,
)


class RecordingPage:
    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on

    def goto(self, url): self._maybe("goto"); 
    def click(self, sel): self._maybe("click")
    def fill(self, sel, val): self._maybe("fill")
    def wait_for_selector(self, sel, timeout=None): self._maybe("wait")
    def screenshot(self, path): self.calls.append(("screenshot", path))

    def _maybe(self, name):
        self.calls.append((name,))
        if self._fail_on == name:
            raise RuntimeError(f"boom at {name}")


def _make_job(steps):
    return FullJob(
        name="t", browser=BrowserConfig(headless=True),
        session=SessionConfig(storage_state="./.session/t.json", reuse=False),
        credentials=Credentials(username="u", password="p"),
        start_url="https://x.test/login",
        steps=steps, output=OutputConfig(dir="./downloads"),
    )


def test_run_job_dispatches_all_steps(monkeypatch):
    page = RecordingPage()
    monkeypatch.setattr(executor, "open_browser", lambda *a, **kw: _ctxmgr(page))
    monkeypatch.setenv("U", "u"); monkeypatch.setenv("P", "p")
    job = _make_job([
        Step(action="navigate", url="https://x.test"),
        Step(action="click", selector="#a"),
    ])
    job = job.model_copy(update={"credentials": Credentials(username="${U}", password="${P}")})
    run_job(job, now=datetime(2026, 6, 15))
    names = [c[0] for c in page.calls]
    assert "goto" in names and "click" in names


def test_run_job_screenshot_on_error(monkeypatch, tmp_path):
    page = RecordingPage(fail_on="click")
    monkeypatch.setattr(executor, "open_browser", lambda *a, **kw: _ctxmgr(page))
    monkeypatch.setattr(executor, "screenshot", lambda p, n, i, d=tmp_path: d / f"{n}_{i}.png")
    job = _make_job([Step(action="click", selector="#a")])
    with pytest.raises(JobError) as exc:
        run_job(job, now=datetime(2026, 6, 15))
    assert "Step 0" in str(exc.value)


def test_run_job_missing_credential_raises(monkeypatch):
    monkeypatch.delenv("NOPE_U", raising=False)
    monkeypatch.setattr(executor, "open_browser", lambda **kw: _ctxmgr(RecordingPage()))
    job = _make_job([Step(action="navigate", url="https://x.test")])
    job = job.model_copy(update={"credentials": Credentials(username="${NOPE_U}", password="p")})
    with pytest.raises(Exception):
        run_job(job, now=datetime(2026, 6, 15))


class _Ctx:
    def __enter__(self): return None
    def __exit__(self, *a): return False


def _ctxmgr(page):
    c = _Ctx()
    # 模拟 contextmanager:返回的对象 yield page
    class Mgr:
        def __enter__(self): return page
        def __exit__(self, *a): return False
    return Mgr()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_executor.py -v`
Expected: FAIL —— `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `crawl_tools/runtime/executor.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_executor.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add crawl_tools/runtime/executor.py tests/test_executor.py
git commit -m "feat(executor): run_job resolves creds, dispatches steps, screenshots on error"
```

---

## Task 10: CLI（`cli.py`）

**Files:**
- Create: `crawl_tools/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 写失败测试 `tests/test_cli.py`**

```python
from pathlib import Path

from typer.testing import CliRunner

from crawl_tools.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
runner = CliRunner()


def test_dry_run_prints_plan(monkeypatch, tmp_path):
    # 让凭据可解析
    monkeypatch.setenv("ERP_A_USER", "u")
    monkeypatch.setenv("ERP_A_PASSWORD", "p")
    result = runner.invoke(app, ["dry-run", str(FIXTURES / "job.yaml"), "--platforms-dir", str(FIXTURES)])
    assert result.exit_code == 0, result.stdout
    assert "erp-a-sales" in result.stdout
    assert "login" in result.stdout
    assert "download" in result.stdout


def test_build_writes_script(tmp_path, monkeypatch):
    monkeypatch.setenv("ERP_A_USER", "u"); monkeypatch.setenv("ERP_A_PASSWORD", "p")
    result = runner.invoke(app, ["build", str(FIXTURES / "job.yaml"),
                                 "--platforms-dir", str(FIXTURES),
                                 "--dest", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "erp-a-sales.py").exists()


def test_list_outputs_platforms_and_jobs(monkeypatch):
    result = runner.invoke(app, ["list", "--platforms-dir", str(FIXTURES), "--jobs-dir", str(FIXTURES)])
    assert result.exit_code == 0, result.stdout
    assert "erp-a" in result.stdout
    assert "job" in result.stdout  # fixture 里 job.yaml


def test_init_scaffolds_job(tmp_path):
    result = runner.invoke(app, ["init", "newjob", "--dir", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "newjob.yaml").exists()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL —— `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `crawl_tools/cli.py`**

```python
from pathlib import Path
from textwrap import dedent

import typer

from crawl_tools.compiler.codegen import write_script
from crawl_tools.credentials import check_resolvable
from crawl_tools.loader import JOBS_DIR, PLATFORMS_DIR, load_and_merge

app = typer.Typer(help="YAML 驱动的爬虫:流程描述 -> Playwright 代码 -> 数据下载", add_completion=False)


@app.command("list")
def list_cmd(
    platforms_dir: Path = typer.Option(PLATFORMS_DIR, "--platforms-dir"),
    jobs_dir: Path = typer.Option(JOBS_DIR, "--jobs-dir"),
):
    """列出可用的平台与任务。"""
    typer.echo("Platforms:")
    if platforms_dir.is_dir():
        for p in sorted(platforms_dir.glob("*.y*ml")):
            typer.echo(f"  - {p.stem}")
    typer.echo("Jobs:")
    if jobs_dir.is_dir():
        for j in sorted(jobs_dir.glob("*.y*ml")):
            typer.echo(f"  - {j.stem}")


@app.command("dry-run")
def dry_run(
    job: Path = typer.Argument(...),
    platforms_dir: Path = typer.Option(PLATFORMS_DIR, "--platforms-dir"),
):
    """校验 job+platform,打印执行计划(不打开浏览器)。"""
    full = load_and_merge(job, platforms_dir=platforms_dir)
    typer.echo(f"Job: {full.name}")
    typer.echo(f"Start URL: {full.start_url}")
    typer.echo(f"Browser headless: {full.browser.headless}")
    typer.echo(f"Session: {full.session.storage_state} (reuse={full.session.reuse})")
    try:
        check_resolvable([full.credentials.username, full.credentials.password])
        typer.echo("Credentials: OK (placeholders resolvable)")
    except Exception as e:
        typer.echo(f"Credentials: MISSING -> {e}")
    typer.echo("Steps:")
    for i, step in enumerate(full.steps):
        kv = step.model_dump(exclude_none=True)
        kv.pop("action", None)
        typer.echo(f"  {i}. {step.action}  " + " ".join(f"{k}={v}" for k, v in kv.items()))


@app.command("build")
def build(
    job: Path = typer.Argument(...),
    platforms_dir: Path = typer.Option(PLATFORMS_DIR, "--platforms-dir"),
    dest: Path = typer.Option("generated", "--dest"),
):
    """校验并导出可运行的 .py 脚本(不执行)。"""
    full = load_and_merge(job, platforms_dir=platforms_dir)
    path = write_script(full, dest_dir=dest)
    typer.echo(f"Generated: {path}")


@app.command("run")
def run(
    job: Path = typer.Argument(...),
    platforms_dir: Path = typer.Option(PLATFORMS_DIR, "--platforms-dir"),
):
    """校验、生成代码、执行 —— 下载数据。"""
    from crawl_tools.runtime.executor import run_job

    full = load_and_merge(job, platforms_dir=platforms_dir)
    path = write_script(full)
    typer.echo(f"Generated: {path}")
    run_job(full)


JOB_TEMPLATE = dedent("""\
    name: {name}
    platform: CHANGE_ME       # 引用 platforms/<name>.yaml
    steps:
      - action: navigate
        url: https://example.test/page
      - action: wait
        selector: "table.data"
      # 模式一:站点自带导出按钮
      - action: download
        selector: "button.export"
        save_as: {name}-{{date}}.xlsx
      # 模式二(无导出按钮):extract_table -> export
      # - action: extract_table
      #   selector: "table.data"
      # - action: export
      #   save_as: {name}-{{date}}.xlsx
    output:
      dir: ./downloads
    """)


@app.command("init")
def init(
    name: str = typer.Argument(...),
    dir: Path = typer.Option(JOBS_DIR, "--dir"),
):
    """脚手架:生成新任务 YAML 模板。"""
    dir.mkdir(parents=True, exist_ok=True)
    path = dir / f"{name}.yaml"
    path.write_text(JOB_TEMPLATE.format(name=name), encoding="utf-8")
    typer.echo(f"Created: {path}")
    typer.echo("Next: edit platform reference and steps, then `crawl dry-run <file>`.")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_cli.py -v`
Expected: 4 passed

- [ ] **Step 5: 烟雾测试 CLI 已注册**

Run: `crawl --help`
Expected: 打印帮助，列出 `list`/`dry-run`/`build`/`run`/`init` 子命令。

- [ ] **Step 6: 提交**

```bash
git add crawl_tools/cli.py tests/test_cli.py
git commit -m "feat(cli): list/dry-run/build/run/init commands via typer"
```

---

## Task 11: 示例平台与任务 + 端到端冒烟

**Files:**
- Create: `platforms/erp-a.yaml`
- Create: `jobs/erp-a-sales.yaml`

- [ ] **Step 1: 写 `platforms/erp-a.yaml`**

```yaml
name: erp-a
login:
  url: https://erp-a.example.com/login
  username_selector: "input[name='username']"
  password_selector: "input[name='password']"
  submit_selector: "button[type='submit']"
  success_selector: "a.logout"
  captcha:
    manual:
      reason: "若出现验证码请手动完成"
      wait_for:
        selector: "a.logout"
        timeout: 180
credentials:
  username: ${ERP_A_USER}
  password: ${ERP_A_PASSWORD}
session:
  storage_state: ./.session/erp-a.json
  reuse: true
browser:
  headless: false
```

- [ ] **Step 2: 写 `jobs/erp-a-sales.yaml`**

```yaml
name: erp-a-sales
platform: erp-a
steps:
  - action: navigate
    url: https://erp-a.example.com/reports/sales
  - action: wait
    selector: "table.report-table"
  - action: download
    selector: "button.export-excel"
    save_as: erp-a-sales-{date}.xlsx
output:
  dir: ./downloads
```

- [ ] **Step 3: 全量单测**

Run: `pytest -v`
Expected: 全部非 slow 测试通过（schema/credentials/output/loader/codegen/actions/executor/cli）。

- [ ] **Step 4: dry-run 冒烟**

Run: `crawl dry-run jobs/erp-a-sales.yaml`
Expected: 打印 `erp-a-sales` 的执行计划（navigate→login→manual→navigate→wait→download），凭据行显示 OK 或 MISSING（取决于 .env）。

- [ ] **Step 5: build 冒烟**

Run: `crawl build jobs/erp-a-sales.yaml`
Expected: 输出 `Generated: generated/erp-a-sales.py`，文件存在且包含 `run_job`。

- [ ] **Step 6: 提交**

```bash
git add platforms/ jobs/
git commit -m "docs: example platform (erp-a) and job (erp-a-sales)"
```

---

## Task 12（可选,slow）: 本地样例站端到端集成

> 仅当需要一个无外部依赖的"真能跑"演示时实现。标记 `slow`,默认不跑。

**Files:**
- Create: `tests/test_e2e_sample.py`
- Create: `tests/fixtures/sample_site.html`

- [ ] **Step 1: 写样例站 `tests/fixtures/sample_site.html`**

```html
<!DOCTYPE html>
<html><body>
  <form id="login">
    <input name="username"><input name="password" type="password">
    <button type="submit">Login</button>
  </form>
  <a class="logout" style="display:none">Logout</a>
  <table id="t"><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>
</body></html>
```

- [ ] **Step 2: 写 slow 测试 `tests/test_e2e_sample.py`**

```python
import pytest
from playwright.sync_api import sync_playwright

from crawl_tools.runtime.actions import Context, extract_table, navigate
from crawl_tools.schema import Step

FIXTURE = "file://" + str((__import__("pathlib").Path(__file__).parent / "fixtures" / "sample_site.html").resolve())


@pytest.mark.slow
def test_navigate_and_extract_table_from_local_html(tmp_path):
    from datetime import datetime
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()
        ctx = Context(username="u", password="p", output_dir=str(tmp_path), now=datetime.now())
        navigate(page, Step(action="navigate", url=FIXTURE), ctx)
        extract_table(page, Step(action="extract_table", selector="#t"), ctx)
        assert list(ctx.last_table["a"]) == [1]
        assert list(ctx.last_table["b"]) == [2]
        browser.close()
```

- [ ] **Step 3: 运行 slow 测试**

Run: `pytest tests/test_e2e_sample.py -v -m slow`
Expected: 1 passed（验证 actions 对真实 DOM 工作正常）。

- [ ] **Step 4: 提交**

```bash
git add tests/test_e2e_sample.py tests/fixtures/sample_site.html
git commit -m "test: slow e2e integration against local sample site"
```

---

## 完成准则

- [ ] `pytest -v` 全绿（非 slow）
- [ ] `crawl --help` 列出 5 个子命令
- [ ] `crawl dry-run jobs/erp-a-sales.yaml` 正确打印执行计划
- [ ] `crawl build jobs/erp-a-sales.yaml` 生成可编译的 `.py`
- [ ] `platforms/` 与 `jobs/` 各有一个可读示例
- [ ] 每个任务独立提交,历史清晰

## 后续演进（不在本计划）

- 会话过期自动检测（spec §9"检测到登录页/失败标志 → 提示重新走 manual"）：当前每次运行都重跑 login，过期会自然触发重登；"失败标志检测+提示重过码"的 UX 细化推迟
- `crawl from-text`:LLM 把自然语言 → 同一份 job YAML → 走现有管线（零改动）
- 验证码自动解码:`solve_captcha` 动作 + provider(ddddocr / 2captcha)
- OS keyring 凭据、Web UI、任务调度、并发
