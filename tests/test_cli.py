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
