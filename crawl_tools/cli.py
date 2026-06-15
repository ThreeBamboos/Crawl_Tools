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
