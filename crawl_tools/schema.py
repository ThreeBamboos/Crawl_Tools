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
