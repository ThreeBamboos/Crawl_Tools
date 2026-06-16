# Crawl_Tools

用 YAML 描述爬取流程，工具自动生成 Python 代码、登录目标网站、下载数据表。

> 把"我要登录某系统、点几下、下载某张报表"写成结构化配置，工具替你跑 Playwright。

---

## 这个工具解决什么问题

你有多个平台、多个流程，每个都要：登录 → 导航 → 下载数据表。手写爬虫重复、易错。

Crawl_Tools 让你：

- **登录逻辑只写一次**（一个平台定义），被该平台下任意任务复用
- **每个取数流程一个任务文件**，互不干扰，按需运行
- **生成可读、可改的 Python 代码**（不是黑盒），也能直接执行一步拿文件
- **凭据不入库**（YAML 里只有占位符），验证码用人在回路兜底

---

## 一、安装

需要 Python 3.10+（已在 3.14 验证）。

```bash
pip install -e ".[dev]"
playwright install chromium   # 下载浏览器内核（约 300MB，仅首次）
```

验证安装：

```bash
crawl --help        # 应列出 list/dry-run/build/run/init
crawl list          # 列出已有的平台与任务
```

---

## 二、核心概念：平台 与 任务

工具的输入是两类 YAML 文件：

| 文件 | 位置 | 内容 | 复用 |
|---|---|---|---|
| **平台** | `platforms/<名字>.yaml` | 登录页 + 选择器 + 凭据 + 会话 + 浏览器配置 | 一个平台被多个任务复用 |
| **任务** | `jobs/<名字>.yaml` | 引用某平台 + 取数步骤 + 输出目录 | 每个流程一个，独立运行 |

**任务运行时**，工具会把引用的"平台登录步骤"自动拼到任务步骤前面，组成完整流程：

```
[平台] navigate 登录页 → login 填账密 → (可选) manual 过验证码
   ↓ 衔接
[任务] 你写的 navigate / wait / download ... 步骤
```

---

## 三、快速开始（5 分钟）

仓库自带示例：平台 `erp-a` + 任务 `erp-a-sales`。

**1. 配置凭据**（YAML 里不写明文，用环境变量）

复制模板、填入真实账号密码：

```bash
cp .env.example .env
```

编辑 `.env`：

```
ERP_A_USER=你的用户名
ERP_A_PASSWORD=你的密码
```

**2. 看执行计划**（不打开浏览器，纯校验）

```bash
crawl dry-run jobs/erp-a-sales.yaml
```

输出会列出完整步骤序列、起始 URL、会话路径、凭据是否就绪。

**3. 生成代码**（产出可读 `.py`，不执行）

```bash
crawl build jobs/erp-a-sales.yaml
# → generated/erp-a-sales.py
```

**4. 实跑**（生成代码 + 执行，下载数据到 ./downloads）

```bash
crawl run jobs/erp-a-sales.yaml
```

> 原型阶段示例站点是假地址（`erp-a.example.com`），真实使用前请把选择器和 URL 换成你自己的（见第五节）。

---

## 四、平台定义详解

文件：`platforms/<名字>.yaml`（文件名 = 平台名，任务按此引用）。

```yaml
name: erp-a                       # 平台名（任务用 platform: erp-a 引用）

login:                            # 登录配置
  url: https://erp-a.example.com/login
  username_selector: "input[name='username']"   # 账号输入框
  password_selector: "input[name='password']"   # 密码输入框
  submit_selector: "button[type='submit']"      # 登录按钮
  success_selector: "a.logout"                  # 登录成功后出现的元素（判定登录成功）
  captcha:                        # 可选：登录后可能弹验证码，加这段兜底
    manual:
      reason: "若出现验证码请手动完成"
      wait_for:
        selector: "a.logout"      # 过码成功（=登录完成）的标志
        timeout: 180              # 给 180 秒手动操作

credentials:                      # 凭据：只写占位符，绝不写明文
  username: ${ERP_A_USER}
  password: ${ERP_A_PASSWORD}

session:                          # 会话复用：登录一次后存 cookies，下次免登录
  storage_state: ./.session/erp-a.json
  reuse: true

browser:
  headless: false                 # 有验证码/HITL 时必须 false（要看到浏览器）
```

**字段说明**

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | ✅ | 平台名 |
| `login.url` | ✅ | 登录页地址 |
| `login.*_selector` | ✅ | 账号/密码/提交/成功元素的选择器 |
| `login.captcha` | ❌ | 登录后可能弹验证码时加，人工兜底 |
| `credentials.*` | ✅ | 用 `${VAR}` 占位，运行时从环境变量/`.env` 解析 |
| `session.storage_state` | ✅ | 会话缓存文件路径；建议每平台一个，互不污染 |
| `session.reuse` | ❌ | 默认 `true`，复用已存会话 |
| `browser.headless` | ❌ | 默认 `false`；有 `manual` 步骤时必须 `false` |

---

## 五、任务定义详解

文件：`jobs/<名字>.yaml`。

```yaml
name: erp-a-sales                 # 任务名（生成代码的文件名也用它）
platform: erp-a                   # 引用哪个平台（自动拼接登录步骤）

steps:                            # 只写"登录之后"的取数步骤
  - action: navigate
    url: https://erp-a.example.com/reports/sales
  - action: wait
    selector: "table.report-table"
  - action: download
    selector: "button.export-excel"
    save_as: erp-a-sales-{date}.xlsx

output:
  dir: ./downloads                # 下载/导出文件的存放目录
```

**文件名占位符**：`save_as` 支持 `{date}`（今日 `YYYY-MM-DD`）和 `{timestamp}`（`YYYYMMDD-HHMMSS`），运行时替换。

> 同平台再加流程：新建 `jobs/erp-a-inventory.yaml`，同样写 `platform: erp-a`，只改取数步骤。
> 跨平台：新建 `platforms/crm.yaml` + `jobs/crm-leads.yaml`。任意数量、互不干扰。

---

## 六、动作清单

任务 `steps` 里每条是一个动作。选择器用 CSS 选择器（如 `"button.export"`、`"#login"`、`"table.data td"`）。

| 动作 | 作用 | 关键字段 |
|---|---|---|
| `navigate` | 打开 URL | `url` |
| `wait` | 等元素出现/超时 | `selector`、`timeout`(秒,可选) |
| `click` | 点击元素 | `selector` |
| `fill` | 填输入框（如日期范围） | `selector`、`value` |
| `select` | 选下拉项 | `selector`、`value` |
| `download` | **点击按钮并截获下载**（自包含） | `selector`(要点的按钮)、`save_as`、`timeout`(可选) |
| `extract_table` | 抓 HTML `<table>` 到内存 | `selector` |
| `export` | 把上一步的表格导出文件 | `save_as`（格式按后缀 `.xlsx`/`.csv`） |
| `manual` | 暂停等人工（过验证码/特殊操作） | `wait_for.selector`、`wait_for.timeout`、`reason`(可选) |
| `login` | 填账密+提交+等成功（**通常不用手写**，由平台自动生成） | — |

> **`download` 是自包含的**：它会自己点 `selector` 指向的按钮并截获下载文件，不需要在前面单独写 `click`。

---

## 七、两种取数模式

**模式一 · 网站自带导出按钮**（推荐，拿到原始 Excel）

```yaml
steps:
  - action: wait
    selector: "table.report-table"
  - action: download
    selector: "button.export-excel"      # 点这个按钮触发下载
    save_as: sales-{date}.xlsx
```

**模式二 · 无导出按钮，抓页面表格**（自己转 Excel/CSV）

```yaml
steps:
  - action: wait
    selector: "table.report-table"
  - action: extract_table               # 抓表到内存
    selector: "table.report-table"
  - action: export                      # 导出文件
    save_as: sales-{date}.xlsx          # 改 .csv 即出 CSV
```

---

## 八、验证码与会话

**验证码**：登录环节在平台 `login.captcha` 配 `manual`，任务里也可随时插入 `manual`。运行到这里时浏览器暂停、由你手动过码，工具等 `wait_for.selector` 出现后继续。覆盖图形/滑块/点选/reCAPTCHA/短信等各类验证码（人工通杀）。

**会话复用**：首次登录（含过码）成功后，`session.storage_state` 存下 cookies。后续运行若会话仍有效，可少过甚至免过验证码。每平台独立会话文件，互不污染。

---

## 九、凭据管理（安全）

- YAML 里**永不写明文**，统一 `${VAR}` 占位
- 运行时解析顺序：**进程环境变量 → `.env` 文件**
- `.env` 已加入 `.gitignore`（不会提交）；`.env.example` 是模板（会提交）
- `dry-run` / `run` 启动前会校验所有占位变量已就绪，**缺了当场报错**，不会等到登录页才挂
- 每个平台绑定各自的变量名（`ERP_A_USER`、`CRM_USER`…），`.env` 统一收纳

---

## 十、CLI 命令参考

```bash
crawl list                              # 列出所有平台与任务
crawl dry-run <job.yaml>                # 校验 + 打印执行计划（不碰浏览器）
crawl build  <job.yaml> [--dest DIR]    # 生成 .py 脚本（默认到 generated/，不执行）
crawl run    <job.yaml>                 # 生成 + 执行（下载数据）
crawl init   <name> [--dir DIR]         # 脚手架：生成新任务模板（默认到 jobs/）
```

所有命令可用 `--platforms-dir` / `--jobs-dir` 指定平台/任务目录（默认 `platforms/`、`jobs/`）。

---

## 十一、找一个真实站点跑通

1. **找选择器**：浏览器打开目标站登录页 → F12 → 选中账号框/密码框/登录按钮，记下它们的 CSS 选择器（如 `input[name='account']`）。
2. **写平台**：复制 `platforms/erp-a.yaml` 改名（如 `platforms/mysystem.yaml`），填入真实 `login.url` 和选择器、`success_selector`（登录后必然出现的元素，如用户头像、退出链接）。
3. **配凭据**：在 `.env` 加一组变量（如 `MYSYS_USER` / `MYSYS_PASSWORD`），平台 `credentials` 引用它们。
4. **写任务**：`crawl init mysys-report` 生成模板，改 `platform: mysystem`，填取数步骤。
5. **逐步验证**：先 `crawl dry-run` 看计划对不对 → 再 `crawl run` 实跑。
6. **出错了**：看 `logs/` 下自动截图（`<任务名>_<第几步>.png`），定位是哪一步、页面当时长什么样。

---

## 十二、目录结构

```
Crawl_Tools/
  crawl_tools/          # 工具源码
  platforms/            # 平台定义（你写）
  jobs/                 # 任务定义（你写）
  generated/            # 生成的 .py（gitignore）
  downloads/            # 下载的数据（gitignore）
  .session/             # 会话缓存（gitignore）
  logs/                 # 出错截图（gitignore）
  .env                  # 凭据（gitignore，从 .env.example 复制）
```

---

## 十三、常见问题

**Q：`crawl run` 报 `Missing credential env vars`？**
A：`.env` 里对应的变量没填或名字和平台 `credentials` 里的 `${VAR}` 对不上。

**Q：登录后卡住 / 一直不过？**
A：`success_selector` 选错了——它必须是登录成功后才出现的元素。换个必然出现的（如退出按钮、用户名）。

**Q：浏览器一闪而过看不到？**
A：平台设 `browser.headless: false`（有 `manual` 步骤时必须 false）。

**Q：下载的文件名日期不对/想带时间？**
A：`save_as` 用 `{date}`（今日）或 `{timestamp}`（精确到秒）。

**Q：同一个系统要下好几个报表？**
A：写一个平台 + 多个任务，每个任务 `platform:` 指向同一个，只改取数步骤。

---

## 设计文档

- 设计规格：`docs/superpowers/specs/2026-06-14-crawl-tools-design.md`
- 实现计划：`docs/superpowers/plans/2026-06-15-crawl-tools-prototype.md`

## 后续演进（当前未实现）

- `crawl from-text`：自然语言 → YAML（AI 解析层，编译器零改动）
- 验证码自动解码（OCR / 第三方打码插件）
- 会话过期自动检测、OS keyring 凭据、Web UI、任务调度
