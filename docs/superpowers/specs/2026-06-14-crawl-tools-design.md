# Crawl_Tools 设计文档（原型）

- **日期**：2026-06-14
- **阶段**：原型（雏形），后续迭代完善
- **来源需求**：`Demand.md` —— 把流程化文字转化为 Python 爬虫代码，登录后下载数据表

---

## 1. 目标与范围

### 1.1 要解决的问题
用户给一段流程化描述，工具把它转化为可运行的 Python 爬虫代码，自动登录目标站点并下载（或抓取并导出）数据表。

### 1.2 原型目标
用最小可用的形态验证"流程 → 代码 → 下载"这条主线，能在一个真实登录站上跑通端到端。

### 1.3 明确推迟（不在原型实现）
- AI 自然语言解析（`crawl from-text`）—— 原型用结构化 YAML，AI 层作为后期演进
- 验证码自动解码（OCR / 第三方打码服务）—— 原型仅人工兜底
- OS keyring 凭据存储、Web UI、任务调度、并发、分布式

---

## 2. 关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 核心机制 | 模板/结构化编译（确定性） | 原型稳定可控；架构为后期 AI 解析留接口 |
| 运行形态 | 生成代码 + 直接执行，也支持只导出 `.py` | 既兑现"转化为 Python 代码"，又能一步拿文件 |
| 输入交互 | CLI + YAML 指令文件 | 结构清晰、可版本控制；YAML 是唯一真相源 |
| 抓取引擎 | Playwright | 登录 + 动态页 + 下载/抓表都能覆盖 |
| 代码生成策略 | 方案 C：薄生成脚本 + 共享动作库 | 生成代码干净可查、动作库可测可扩、YAML 为契约 |
| 验证码范围 | 仅 HITL `manual` + 会话复用 | 能应对一切验证码、合规、立刻可用 |
| 多任务组织 | 平台 / 任务分离（`platforms/` + `jobs/`） | 多平台多流程天然分离、登录可复用、会话凭据按平台隔离 |

---

## 3. 架构总览

五层处理，单向数据流，每层职责单一、可独立测试：

```
platforms/<name>.yaml   jobs/<name>.yaml        ← 两类输入
        │                    │（job 引用 platform）
        └─────────┬──────────┘
                  ▼
[① Schema 校验 + 合并]   解析两类 YAML；job 引用的 platform 合并进来
                          （登录步骤、凭据、会话、浏览器配置）→ 完整 Job 模型
   │  完整 Job 模型
   ▼
[② 编译器 codegen]  Job → 可读的薄 .py（编排步骤，调用动作库）
   │  generated/<name>.py
   ├───── build 模式：到这一步停止，只写出 .py 文件 ─────┐
   ▼                                                    │
[③ 执行器 executor]  运行 generated/<name>.py            │
   │                                                    │
   ▼                                                    │
[④ 动作库 runtime]  login / navigate / click /           │
│                    wait / fill / select /              │
│                    download / extract_table /          │
│                    export / manual                     │
│       └─► Playwright 浏览器：登录→导航→下载/抓表         │
   │                                                    │
   ▼                                                    │
[⑤ 输出]   downloads/ 放下载文件；或导出 xlsx/csv         │
```

**核心约束**：平台与任务的 YAML 是唯一真相源，编译器与动作库互不耦合。未来 AI 解析层只需产出同一份任务 YAML，① ~ ⑤ 零改动。

---

## 4. DSL：平台与任务

输入分两类 YAML：**平台**（可复用的登录 + 凭据 + 会话）和**任务**（引用平台、只写取数步骤）。任务运行时，① 校验层把引用的平台合并进来，得到完整 Job。

### 4.1 平台定义（`platforms/<name>.yaml` —— 登录只写一次、被多任务复用）

```yaml
# platforms/erp-a.yaml
name: erp-a
login:
  url: https://erp-a.example.com/login
  username_selector: "input[name='username']"
  password_selector: "input[name='password']"
  submit_selector: "button[type='submit']"
  success_selector: "a.logout"        # 登录成功判定元素
  captcha:                             # 可选：登录后若弹验证码，人工兜底
    manual:
      reason: "若出现验证码请手动完成"
      wait_for:
        selector: "a.logout"
        timeout: 180
credentials:                           # 按平台绑定各自环境变量，互不冲突
  username: ${ERP_A_USER}
  password: ${ERP_A_PASSWORD}
session:
  storage_state: ./.session/erp-a.json # 每平台独立会话，互不污染
  reuse: true
browser:
  headless: false                      # HITL 必须 false
```

### 4.2 任务定义（`jobs/<name>.yaml` —— 引用平台、只写取数步骤）

```yaml
# jobs/erp-a-sales.yaml
name: erp-a-sales
platform: erp-a                        # ← 复用上面的登录/凭据/会话
steps:
  - action: navigate
    url: https://erp-a.example.com/reports/sales
  - action: wait
    selector: "table.report-table"
  - action: click
    selector: "button.export-excel"
  - action: download
    save_as: erp-a-sales-{date}.xlsx
output:
  dir: ./downloads
```

> 同平台再加 `jobs/erp-a-inventory.yaml`（同样 `platform: erp-a`）；跨平台加 `platforms/crm.yaml` + `jobs/crm-leads.yaml`。任意数量、互不干扰，运行时各跑各的，**无需"换配置"**。

### 4.3 动作集（runtime 原语，每个对应一个可单测函数）

| 动作 | 作用 | 关键参数 |
|---|---|---|
| `login` | 填账号密码 + 提交 + 等待成功标志（由平台 `login` 块生成） | `username_selector` / `password_selector` / `submit_selector` / `success_selector` |
| `navigate` | 打开 URL | `url` |
| `fill` | 填输入框（如日期范围） | `selector` / `value` |
| `select` | 选下拉项 | `selector` / `value` |
| `click` | 点击元素 | `selector` |
| `wait` | 等元素/超时 | `selector` / `timeout` |
| `download` | 配置浏览器截获下一次下载并保存（由前置 `click` 触发） | `save_as` |
| `extract_table` | 抓 HTML `<table>` → DataFrame | `selector` |
| `export` | DataFrame 写 xlsx/csv | `save_as` / `format` |
| `manual` | 暂停等人工（过验证码等），满足条件后继续 | `wait_for.selector` / `wait_for.timeout` |

### 4.4 取数两种模式
- **模式一 · 原生导出**：点"导出 Excel"按钮 → `download` 截获文件
- **模式二 · 无导出按钮**：`extract_table` 抓表格 → `export` 转 xlsx/csv

> `save_as` / `export` 的文件名支持占位符：`{date}`（本地今日 `YYYY-MM-DD`）、`{timestamp}`（`YYYYMMDD-HHMMSS`），运行时解析。

---

## 5. 验证码处理（HITL + 会话复用）

验证码类型多样（图形/滑块/点选/reCAPTCHA/OTP），无单一全自动方案，且自动绕过第三方验证码存在 ToS/法律风险。

**原型方案**：
1. **HITL `manual` 动作**：执行到此步，浏览器有头可见并暂停，由用户手动过验证码；工具等 `wait_for.selector` 出现后继续。合规（用户在自己账号上过自己的验证码），对所有类型通杀。登录环节的过码在平台 `login.captcha` 块配置；任务里也可随时插入 `manual`。
2. **会话复用 `session.storage_state`**：首次登录（含过码）成功后存 cookies/localStorage，后续运行加载，多数站点不再弹码。

**后期插件化（不在原型）**：`solve_captcha` 动作，provider 可为 `ddddocr`（本地 OCR，简单图形码）或 `2captcha`（第三方打码，付费，注意 ToS）。

---

## 6. 凭据安全

- YAML 内**永不写明文**，统一用 `${VAR}` 占位
- 解析优先级：进程环境变量 → `.env` 文件（`python-dotenv`）
- `.env` 加入 `.gitignore`，提交 `.env.example` 模板
- 每个平台在 `platforms/*.yaml` 绑定各自的 `${VAR}`（如 `ERP_A_USER`、`CRM_USER`），`.env` 统一收纳所有平台凭据
- `dry-run` / `run` 启动前校验所有占位变量已就绪，缺失当场报错

---

## 7. CLI 命令

包名 `crawl_tools`，命令 `crawl`。

| 命令 | 作用 |
|---|---|
| `crawl list` | 列出所有平台与任务，挑着跑（多任务多平台时不用记文件名） |
| `crawl run <job.yaml>` | 校验 → 生成 `.py` → **执行**，拿到下载文件 |
| `crawl build <job.yaml>` | 校验 → 生成 `.py`，**只导出脚本不执行** |
| `crawl dry-run <job.yaml>` | **只校验 + 打印执行计划**，不碰浏览器 |
| `crawl init <name>` | 脚手架：生成新任务模板（或 `crawl init platform <name>` 生成平台模板） |
| `crawl from-text "..."` | *（后期 AI 演进）* 自然语言 → YAML，再走上面任一命令 |

---

## 8. 目录结构

```
Crawl_Tools/
  pyproject.toml
  crawl_tools/
    cli.py              # typer 入口：list/run/build/dry-run/init
    schema.py           # pydantic 模型：Platform/Job/Step/Credentials
    loader.py           # 加载 + 合并 platform 与 job YAML → 完整 Job
    compiler/codegen.py # 完整 Job → generated/<name>.py（薄脚本）
    runtime/
      actions.py        # 动作库（含 manual）
      executor.py       # 运行生成的脚本
      browser.py        # Playwright 封装（含 session storage_state）
    credentials.py      # ${VAR} 解析：env / .env
    output.py           # 下载落盘 / DataFrame 导出 xlsx·csv
  platforms/erp-a.yaml  # 平台定义（可复用登录/凭据/会话）
  jobs/erp-a-sales.yaml # 任务定义（引用 platform，只写取数步骤）
  generated/            # 生成的 .py     ← gitignore
  downloads/            # 下载的数据      ← gitignore
  .session/             # 会话缓存        ← gitignore
  .env.example          # 凭据模板（提交）；.env ← gitignore
  tests/                # test_schema / test_codegen / test_actions
```

---

## 9. 错误处理

- **YAML / Schema 错误**：pydantic 精确指出哪个字段、哪一步
- **dry-run**：执行前全量校验，低成本试错
- **运行时每步**：超时 / 元素未找到 → 自动截图存 `logs/<job>_<step>.png` + 清晰报错
- **任务引用了不存在的 platform**：启动前拦截，提示可用平台名
- **凭据缺失**：启动前拦截
- **会话过期**：检测到登录页 / 失败标志 → 提示重新走 `manual`

---

## 10. 测试策略

- **编译器 / Schema**：纯函数，单测覆盖（合法/非法 YAML、各动作类型、platform/job 合并、缺失 platform 报错）
- **动作库**：离线 HTML fixture 或 Playwright mock 测 `navigate/click/wait/extract_table`
- **TDD**：compiler 和 actions 先写测试再实现（superpowers:test-driven-development）
- **真实浏览器集成**：标记为慢测试，CI 可跳过；配本地样例站跑端到端 job

---

## 11. AI 演进路径（下一步，不在原型）

新增 `crawl from-text`：LLM 把自然语言 → **同一份 YAML** → schema 校验 → 不合规回喂 LLM 修正。因 YAML 是唯一真相源，编译器 / 动作库零改动。

---

## 12. 依赖（原型）

`playwright` · `pydantic` · `pyyaml` · `pandas` + `openpyxl`（表格导出）· `typer`（CLI）· `python-dotenv`（.env）

Python 3.10+。
