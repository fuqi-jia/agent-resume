from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer
from rich import print
from rich.console import Console
from rich.table import Table

from agent_resume.config import load_config, write_default_config
from agent_resume.runner_exec import run_job
from agent_resume.scheduler import collect_prompts, run_job_now, schedule_once, schedule_recurring
from agent_resume.storage import Storage
from agent_resume.system_cron import remove_cron_job

app = typer.Typer(help="Stateful coding-agent scheduler with prompt queue resume.")
schedule_app = typer.Typer()
app.add_typer(schedule_app, name="schedule")
console = Console()


def _storage(config_file: str | None = None) -> Storage:
    cfg = load_config(config_file)
    return Storage(cfg["storage_dir"])


@schedule_app.command("once")
def schedule_once_cmd(
    dir: str = typer.Option(..., "--dir"),
    session: str = typer.Option(..., "--session"),
    time: str = typer.Option(..., "--time"),
    prompt: list[str] = typer.Option(None, "--prompt"),
    template: list[str] = typer.Option(None, "--template"),
    prompt_file: list[str] = typer.Option(None, "--prompt-file"),
    prompt_dir: str | None = typer.Option(None, "--prompt-dir"),
    queue_mode: str = typer.Option("resume", "--queue-mode"),
    on_prompt_failure: str = typer.Option("stop", "--on-prompt-failure"),
    prompt_interval: int = typer.Option(0, "--prompt-interval"),
    concurrency_policy: str = typer.Option("skip", "--concurrency-policy"),
    config: str | None = typer.Option(None, "--config"),
) -> None:
    prompts = collect_prompts(prompt, template, prompt_file, prompt_dir)
    job = schedule_once(
        project_dir=dir,
        session_id=session,
        time_expr=time,
        prompts=prompts,
        queue_mode=queue_mode,
        on_prompt_failure=on_prompt_failure,
        prompt_interval_seconds=prompt_interval,
        concurrency_policy=concurrency_policy,
        config_file=config,
    )
    print(f"[green]Scheduled once job:[/green] {job.job_id}")


@schedule_app.command("recurring")
def schedule_recurring_cmd(
    dir: str = typer.Option(..., "--dir"),
    session: str = typer.Option(..., "--session"),
    cron: str = typer.Option(..., "--cron"),
    prompt: list[str] = typer.Option(None, "--prompt"),
    template: list[str] = typer.Option(None, "--template"),
    prompt_file: list[str] = typer.Option(None, "--prompt-file"),
    prompt_dir: str | None = typer.Option(None, "--prompt-dir"),
    queue_mode: str = typer.Option("resume", "--queue-mode"),
    on_prompt_failure: str = typer.Option("stop", "--on-prompt-failure"),
    prompt_interval: int = typer.Option(0, "--prompt-interval"),
    concurrency_policy: str = typer.Option("skip", "--concurrency-policy"),
    config: str | None = typer.Option(None, "--config"),
) -> None:
    prompts = collect_prompts(prompt, template, prompt_file, prompt_dir)
    job = schedule_recurring(
        project_dir=dir,
        session_id=session,
        cron_expr=cron,
        prompts=prompts,
        queue_mode=queue_mode,
        on_prompt_failure=on_prompt_failure,
        prompt_interval_seconds=prompt_interval,
        concurrency_policy=concurrency_policy,
        config_file=config,
    )
    print(f"[green]Scheduled recurring job:[/green] {job.job_id}")


@schedule_app.command("from-config")
def schedule_from_config(file: str = typer.Option(..., "--file"), config: str | None = typer.Option(None, "--config")) -> None:
    import yaml

    data = yaml.safe_load(Path(file).expanduser().read_text(encoding="utf-8")) or {}
    prompts = collect_prompts(
        prompt=[data["prompt"]] if data.get("prompt") else [],
        template=[data["template"]] if data.get("template") else [],
        prompt_file=[data["prompt_file"]] if data.get("prompt_file") else [],
        prompt_dir=data.get("prompt_dir"),
    )
    common = dict(
        project_dir=data.get("dir"),
        session_id=data.get("session_id"),
        prompts=prompts,
        queue_mode=data.get("queue_mode"),
        on_prompt_failure=data.get("on_prompt_failure"),
        prompt_interval_seconds=data.get("prompt_interval_seconds"),
        concurrency_policy=data.get("concurrency_policy"),
        config_file=config,
    )
    if data.get("cron"):
        job = schedule_recurring(cron_expr=data["cron"], **common)
    else:
        job = schedule_once(time_expr=data.get("time", "now"), **common)
    print(f"[green]Scheduled from config:[/green] {job.job_id}")


@app.command("list")
def list_jobs(config: str | None = typer.Option(None, "--config")) -> None:
    jobs = _storage(config).load_jobs()
    table = Table(title="agent-resume jobs")
    table.add_column("job_id")
    table.add_column("type")
    table.add_column("status")
    table.add_column("queue")
    table.add_column("index")
    for job in jobs.values():
        table.add_row(job.job_id, job.type, job.status, job.queue_status, str(job.current_prompt_index))
    console.print(table)


@app.command("show")
def show_job(job_id: str, config: str | None = typer.Option(None, "--config")) -> None:
    job = _storage(config).get_job(job_id)
    print(json.dumps(job.to_dict(), indent=2, ensure_ascii=False))


@app.command("queue")
def show_queue(job_id: str, config: str | None = typer.Option(None, "--config")) -> None:
    job = _storage(config).get_job(job_id)
    for idx, p in enumerate(job.prompt_queue, start=1):
        marker = ">>" if idx - 1 == job.current_prompt_index else "  "
        print(f"{marker} [{idx}] {p}")


@app.command("cancel")
def cancel_job(job_id: str, config: str | None = typer.Option(None, "--config")) -> None:
    st = _storage(config)
    job = st.get_job(job_id)
    job.status = "cancelled"
    if job.type == "recurring":
        remove_cron_job(job_id)
    st.upsert_job(job)
    print(f"[yellow]Cancelled[/yellow] {job_id}")


@app.command("pause")
def pause_job(job_id: str, config: str | None = typer.Option(None, "--config")) -> None:
    st = _storage(config)
    job = st.get_job(job_id)
    job.paused = True
    job.status = "paused"
    st.upsert_job(job)
    print(f"[yellow]Paused[/yellow] {job_id}")


@app.command("resume-job")
def resume_job(job_id: str, config: str | None = typer.Option(None, "--config")) -> None:
    st = _storage(config)
    job = st.get_job(job_id)
    job.paused = False
    job.status = "scheduled"
    st.upsert_job(job)
    print(f"[green]Resumed[/green] {job_id}")


@app.command("reset-queue")
def reset_queue(job_id: str, config: str | None = typer.Option(None, "--config")) -> None:
    st = _storage(config)
    job = st.get_job(job_id)
    job.current_prompt_index = 0
    job.queue_status = "pending"
    job.status = "scheduled"
    st.upsert_job(job)
    print(f"[green]Queue reset[/green] {job_id}")


@app.command("run-now")
def run_now(job_id: str, config: str | None = typer.Option(None, "--config")) -> None:
    code = run_job_now(job_id, config)
    raise typer.Exit(code=code)


@app.command("log")
def show_log(job_id: str, prompt_index: int | None = typer.Option(None, "--prompt-index"), config: str | None = typer.Option(None, "--config")) -> None:
    st = _storage(config)
    path = st.log_path(job_id, prompt_index)
    if not path.exists():
        raise typer.BadParameter(f"log not found: {path}")
    print(path.read_text(encoding="utf-8"))


@app.command("init-config")
def init_config(config: str | None = typer.Option(None, "--config")) -> None:
    path = write_default_config(config)
    print(f"[green]Wrote config:[/green] {path}")


@app.command("cleanup")
def cleanup(config: str | None = typer.Option(None, "--config")) -> None:
    st = _storage(config)
    jobs = st.load_jobs()
    valid_runners = {Path(j.runner_script_path).name for j in jobs.values() if j.runner_script_path}
    for script in st.runners_dir.glob("*.sh"):
        if script.name not in valid_runners:
            script.unlink(missing_ok=True)
    print("[green]Cleanup done[/green]")


@app.command("doctor")
def doctor(config: str | None = typer.Option(None, "--config")) -> None:
    cfg = load_config(config)
    st = Storage(cfg["storage_dir"])
    st.ensure_dirs()
    at_ok = shutil.which("at") is not None
    cron_ok = shutil.which("crontab") is not None
    print(f"storage_dir: {st.storage_dir}")
    print(f"at: {'ok' if at_ok else 'missing'}")
    print(f"crontab: {'ok' if cron_ok else 'missing'}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
