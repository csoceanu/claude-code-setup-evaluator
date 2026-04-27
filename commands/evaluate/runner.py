# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "click",
#     "python-dotenv",
#     "httpx",
#     "jinja2",
#     "pyyaml",
# ]
# ///
"""Evaluation runner for AI bots.

Reads eval.yaml, runs questions against targets (Python function, shell command,
or HTTP endpoint), captures results, and saves them as JSON in .eval/runs/.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import re
import shlex
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import click
import httpx
import yaml
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_field(data: dict, path: str) -> Any:
    """Extract a value using dot-notation path."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def get_git_info() -> tuple[str | None, str | None]:
    try:
        git_hash = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        git_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        return git_hash or None, git_branch or None
    except Exception:
        return None, None


def sanitize_label(label: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", label).strip("-")


def env_substitute(value: str) -> str:
    """Replace ${VAR} patterns with environment variable values."""
    def _replace(m: re.Match) -> str:
        return os.environ.get(m.group(1), "")
    return re.sub(r"\$\{([^}]+)\}", _replace, value)


def ensure_eval_dirs(eval_dir: Path) -> Path:
    runs_dir = eval_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    gitignore = eval_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")
    return runs_dir


def load_index(runs_dir: Path) -> dict:
    index_path = runs_dir / "index.json"
    if index_path.exists():
        return json.loads(index_path.read_text())
    return {"runs": []}


def save_index(runs_dir: Path, index: dict) -> None:
    (runs_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")


def next_run_number(index: dict) -> int:
    if not index["runs"]:
        return 1
    return max(r["run_number"] for r in index["runs"]) + 1


def load_questions(questions: list[str] | None, questions_file: str | None) -> list[str]:
    if questions:
        return questions
    if not questions_file:
        raise click.ClickException("No questions or questions_file specified in config")
    p = Path(questions_file)
    if not p.exists():
        raise click.ClickException(f"Questions file not found: {questions_file}")
    suffix = p.suffix.lower()
    if suffix == ".txt":
        lines = p.read_text().splitlines()
        return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
    elif suffix in (".yaml", ".yml"):
        return yaml.safe_load(p.read_text())
    elif suffix == ".json":
        return json.loads(p.read_text())
    else:
        raise click.ClickException(f"Unsupported questions file format: {suffix}")


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------

def parse_config(config_path: Path) -> dict:
    """Parse eval.yaml and normalize into a standard structure."""
    if not config_path.exists():
        raise click.ClickException(f"Config file not found: {config_path}")
    cfg = yaml.safe_load(config_path.read_text())
    if cfg is None:
        raise click.ClickException(f"Empty config file: {config_path}")

    settings = cfg.get("settings", {})
    result = {
        "timeout": settings.get("timeout", 30),
        "env_file": settings.get("env_file") or cfg.get("env_file"),
        "start_command": settings.get("start_command") or cfg.get("start_command"),
        "start_wait": settings.get("start_wait", 0) or cfg.get("start_wait", 0),
        "stop_command": settings.get("stop_command") or cfg.get("stop_command"),
        "version": cfg.get("version"),
        "targets": [],
    }

    if "targets" in cfg:
        for name, tgt_cfg in cfg["targets"].items():
            result["targets"].append(_parse_target(name, tgt_cfg))
    elif "target" in cfg:
        tgt_cfg = dict(cfg["target"])
        tgt_cfg["fields"] = cfg.get("fields", {})
        tgt_cfg["questions"] = cfg.get("questions")
        tgt_cfg["questions_file"] = cfg.get("questions_file")
        name = tgt_cfg.get("module") or tgt_cfg.get("command") or tgt_cfg.get("endpoint", "default")
        result["targets"].append(_parse_target(name, tgt_cfg))
    else:
        raise click.ClickException("Config must have 'target' or 'targets' key")

    return result


def _parse_target(name: str, cfg: dict) -> dict:
    if "module" in cfg:
        target_type = "module"
        target_value = cfg["module"]
    elif "command" in cfg:
        target_type = "command"
        target_value = cfg["command"]
    elif "endpoint" in cfg:
        target_type = "endpoint"
        target_value = cfg["endpoint"]
    else:
        raise click.ClickException(f"Target '{name}' must specify module, command, or endpoint")

    return {
        "name": name,
        "type": target_type,
        "value": target_value,
        "fields": cfg.get("fields", {}),
        "questions": cfg.get("questions"),
        "questions_file": cfg.get("questions_file"),
        "request_field": cfg.get("request_field", "question"),
        "headers": cfg.get("headers", {}),
    }


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def execute_module(target: dict, question: str, timeout: int) -> dict:
    module_path = target["value"]
    parts = module_path.rsplit(".", 1)
    if len(parts) != 2:
        return {"answer": None, "error": f"Invalid module path: {module_path}", "latency_ms": 0, "fields": {}}

    mod_name, func_name = parts
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        mod = importlib.import_module(mod_name)
        func = getattr(mod, func_name)
    except Exception as e:
        return {"answer": None, "error": f"Import error: {e}", "latency_ms": 0, "fields": {}}

    start = time.perf_counter()
    try:
        if inspect.iscoroutinefunction(func):
            result = asyncio.run(func(question))
        else:
            result = func(question)
        latency = int((time.perf_counter() - start) * 1000)
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"answer": None, "error": str(e), "latency_ms": latency, "fields": {}}

    return _process_result(result, target, latency)


def execute_command(target: dict, question: str, timeout: int, capture_logs: bool) -> dict:
    cmd = target["value"].replace("{question}", shlex.quote(question))
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        latency = int((time.perf_counter() - start) * 1000)
    except subprocess.TimeoutExpired:
        latency = int((time.perf_counter() - start) * 1000)
        return {"answer": None, "error": f"Timeout after {timeout}s", "latency_ms": latency, "fields": {},
                "stdout": "", "stderr": ""}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"answer": None, "error": str(e), "latency_ms": latency, "fields": {},
                "stdout": "", "stderr": ""}

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if proc.returncode != 0:
        return {
            "answer": None,
            "error": f"Exit code {proc.returncode}: {stderr.strip()}" if stderr.strip() else f"Exit code {proc.returncode}",
            "latency_ms": latency,
            "fields": {},
            "stdout": stdout if capture_logs else "",
            "stderr": stderr if capture_logs else "",
        }

    # Try parsing stdout as JSON
    try:
        data = json.loads(stdout)
        result = _process_result(data, target, latency)
    except (json.JSONDecodeError, ValueError):
        result = _process_result(stdout.strip(), target, latency)

    if capture_logs:
        result["stdout"] = stdout
        result["stderr"] = stderr
    return result


def execute_endpoint(target: dict, question: str, timeout: int) -> dict:
    url = target["value"]
    request_field = target.get("request_field", "question")
    headers = {k: env_substitute(v) for k, v in target.get("headers", {}).items()}

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json={request_field: question}, headers=headers)
        latency = int((time.perf_counter() - start) * 1000)
    except httpx.TimeoutException:
        latency = int((time.perf_counter() - start) * 1000)
        return {"answer": None, "error": f"HTTP timeout after {timeout}s", "latency_ms": latency, "fields": {}}
    except httpx.ConnectError as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"answer": None, "error": f"Connection error: {e}", "latency_ms": latency, "fields": {}}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"answer": None, "error": f"HTTP error: {e}", "latency_ms": latency, "fields": {}}

    if resp.status_code >= 300:
        return {
            "answer": None,
            "error": f"HTTP {resp.status_code}: {resp.text[:500]}",
            "latency_ms": latency,
            "fields": {},
        }

    try:
        data = resp.json()
    except Exception:
        return {"answer": resp.text.strip(), "error": None, "latency_ms": latency, "fields": {}}

    return _process_result(data, target, latency)


def _process_result(result: Any, target: dict, latency: int) -> dict:
    fields_map = target.get("fields", {})
    if isinstance(result, str):
        return {"answer": result, "error": None, "latency_ms": latency, "fields": {}}
    if isinstance(result, dict):
        answer = extract_field(result, fields_map["answer"]) if "answer" in fields_map else result.get("answer")
        extracted = {}
        for field_name, field_path in fields_map.items():
            if field_name == "answer":
                continue
            extracted[field_name] = extract_field(result, field_path)
        return {"answer": answer, "error": None, "latency_ms": latency, "fields": extracted}
    return {"answer": str(result), "error": None, "latency_ms": latency, "fields": {}}


def run_target(target: dict, timeout: int, capture_logs: bool) -> list[dict]:
    questions = load_questions(target.get("questions"), target.get("questions_file"))
    results = []
    for i, question in enumerate(questions):
        click.echo(f"  [{i + 1}/{len(questions)}] {question[:60]}{'...' if len(question) > 60 else ''}", err=True)

        if target["type"] == "module":
            r = execute_module(target, question, timeout)
        elif target["type"] == "command":
            r = execute_command(target, question, timeout, capture_logs)
        elif target["type"] == "endpoint":
            r = execute_endpoint(target, question, timeout)
        else:
            r = {"answer": None, "error": f"Unknown target type: {target['type']}", "latency_ms": 0, "fields": {}}

        status = "ERR" if r.get("error") else "OK"
        click.echo(f"         {status} ({r['latency_ms']}ms)", err=True)

        results.append({
            "index": i,
            "question": question,
            "answer": r.get("answer"),
            "latency_ms": r["latency_ms"],
            "error": r.get("error"),
            "fields": r.get("fields", {}),
            "stdout": r.get("stdout", ""),
            "stderr": r.get("stderr", ""),
        })
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Evaluation runner for AI bots."""


@cli.command()
@click.option("--config", "config_path", default="eval.yaml", type=click.Path(), help="Path to eval config file")
@click.option("--version", "version_label", default=None, help="Version label for this run")
@click.option("--target", "target_name", default=None, help="Run only this target (for multi-target configs)")
@click.option("--eval-dir", default=".eval", type=click.Path(), help="Eval output directory")
@click.option("--timeout", default=None, type=int, help="Timeout per question in seconds")
@click.option("--no-logs", is_flag=True, help="Skip stdout/stderr capture")
def run(config_path: str, version_label: str | None, target_name: str | None,
        eval_dir: str, timeout: int | None, no_logs: bool):
    """Execute evaluation and save results."""
    cfg = parse_config(Path(config_path))
    capture_logs = not no_logs
    effective_timeout = timeout or cfg["timeout"]
    version = version_label or cfg.get("version")

    # Load env
    env_file = cfg.get("env_file")
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    # Filter targets
    targets = cfg["targets"]
    if target_name:
        targets = [t for t in targets if t["name"] == target_name]
        if not targets:
            raise click.ClickException(f"Target '{target_name}' not found in config")

    eval_path = Path(eval_dir)
    runs_dir = ensure_eval_dirs(eval_path)
    index = load_index(runs_dir)
    git_hash, git_branch = get_git_info()

    # Start command
    start_proc = None
    if cfg.get("start_command"):
        click.echo(f"Starting: {cfg['start_command']}", err=True)
        start_proc = subprocess.Popen(cfg["start_command"], shell=True)
        wait = cfg.get("start_wait", 0)
        if wait:
            click.echo(f"Waiting {wait}s for startup...", err=True)
            time.sleep(wait)

    all_run_data = []
    try:
        for target in targets:
            click.echo(f"\nTarget: {target['name']} ({target['type']})", err=True)
            run_number = next_run_number(index)

            # Build run ID
            parts = [f"{run_number:03d}"]
            if version:
                parts.append(sanitize_label(version))
            if len(cfg["targets"]) > 1:
                parts.append(sanitize_label(target["name"]))
            run_id = "_".join(parts)

            results = run_target(target, effective_timeout, capture_logs)

            # Compute summary
            passed = sum(1 for r in results if r["error"] is None)
            failed = len(results) - passed
            latencies = [r["latency_ms"] for r in results]
            avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0
            total_tokens = sum(r["fields"].get("tokens", 0) or 0 for r in results)

            if not capture_logs:
                for r in results:
                    r.pop("stdout", None)
                    r.pop("stderr", None)

            run_data = {
                "run_id": run_id,
                "run_number": run_number,
                "version": version,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "git_hash": git_hash,
                "git_branch": git_branch,
                "target": target["value"],
                "target_type": target["type"],
                "summary": {
                    "total": len(results),
                    "passed": passed,
                    "failed": failed,
                    "avg_latency_ms": avg_latency,
                    "total_tokens": total_tokens,
                },
                "results": results,
            }

            # Save run file
            filename = f"run_{run_id}.json"
            (runs_dir / filename).write_text(json.dumps(run_data, indent=2, default=str) + "\n")

            # Update index
            index["runs"].append({
                "run_id": run_id,
                "run_number": run_number,
                "version": version,
                "target": target["value"],
                "timestamp": run_data["timestamp"],
                "git_hash": git_hash,
                "total": len(results),
                "passed": passed,
                "avg_latency_ms": avg_latency,
            })
            save_index(runs_dir, index)

            all_run_data.append(run_data)

            click.echo(f"  Saved: {filename} ({passed}/{len(results)} passed, avg {avg_latency}ms)", err=True)

    except KeyboardInterrupt:
        click.echo("\nInterrupted — saving partial results", err=True)
        save_index(runs_dir, index)
    finally:
        if cfg.get("stop_command"):
            click.echo(f"Stopping: {cfg['stop_command']}", err=True)
            subprocess.run(cfg["stop_command"], shell=True)
        if start_proc and start_proc.poll() is None:
            start_proc.terminate()

    # Output JSON to stdout for machine consumption
    output = all_run_data[0] if len(all_run_data) == 1 else all_run_data
    click.echo(json.dumps(output, indent=2, default=str))

    # Human summary to stderr
    click.echo("", err=True)
    for rd in all_run_data:
        s = rd["summary"]
        click.echo(
            f"Run {rd['run_id']}: {s['passed']}/{s['total']} passed, "
            f"{s['failed']} failed, avg {s['avg_latency_ms']}ms",
            err=True,
        )


@cli.command("list")
@click.option("--eval-dir", default=".eval", type=click.Path(), help="Eval output directory")
def list_runs(eval_dir: str):
    """Show all runs."""
    runs_dir = Path(eval_dir) / "runs"
    index = load_index(runs_dir)
    if not index["runs"]:
        click.echo("No runs found.")
        return

    click.echo(f"{'RUN':<8} {'ID':<25} {'VERSION':<15} {'TARGET':<30} {'PASSED':<10} {'AVG MS':<10} {'TIMESTAMP'}")
    click.echo("-" * 120)
    for r in index["runs"]:
        click.echo(
            f"{r['run_number']:<8} "
            f"{r['run_id']:<25} "
            f"{(r.get('version') or '-'):<15} "
            f"{r['target'][:28]:<30} "
            f"{r['passed']}/{r['total']:<8} "
            f"{r['avg_latency_ms']:<10} "
            f"{r['timestamp']}"
        )


@cli.command()
@click.argument("run1", required=False, type=int)
@click.argument("run2", required=False, type=int)
@click.option("--eval-dir", default=".eval", type=click.Path(), help="Eval output directory")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def diff(run1: int | None, run2: int | None, eval_dir: str, as_json: bool):
    """Compare two runs."""
    runs_dir = Path(eval_dir) / "runs"
    index = load_index(runs_dir)
    if len(index["runs"]) < 2:
        raise click.ClickException("Need at least 2 runs to compare")

    sorted_runs = sorted(index["runs"], key=lambda r: r["run_number"])
    if run1 is None and run2 is None:
        r1_meta, r2_meta = sorted_runs[-2], sorted_runs[-1]
    elif run2 is None:
        r1_meta = next((r for r in sorted_runs if r["run_number"] == run1), None)
        r2_meta = sorted_runs[-1]
        if r1_meta is None:
            raise click.ClickException(f"Run {run1} not found")
    else:
        r1_meta = next((r for r in sorted_runs if r["run_number"] == run1), None)
        r2_meta = next((r for r in sorted_runs if r["run_number"] == run2), None)
        if r1_meta is None:
            raise click.ClickException(f"Run {run1} not found")
        if r2_meta is None:
            raise click.ClickException(f"Run {run2} not found")

    def load_run(meta: dict) -> dict:
        path = runs_dir / f"run_{meta['run_id']}.json"
        if not path.exists():
            raise click.ClickException(f"Run file not found: {path}")
        return json.loads(path.read_text())

    d1, d2 = load_run(r1_meta), load_run(r2_meta)
    q1 = {r["question"]: r for r in d1["results"]}
    q2 = {r["question"]: r for r in d2["results"]}
    all_questions = list(dict.fromkeys(list(q1.keys()) + list(q2.keys())))

    comparisons = []
    for q in all_questions:
        a1 = q1.get(q)
        a2 = q2.get(q)
        comp: dict[str, Any] = {"question": q}
        ans1 = (a1["answer"] or "") if a1 else ""
        ans2 = (a2["answer"] or "") if a2 else ""
        comp["answer_changed"] = ans1 != ans2
        comp["answer_1"] = ans1
        comp["answer_2"] = ans2
        comp["latency_1"] = a1["latency_ms"] if a1 else None
        comp["latency_2"] = a2["latency_ms"] if a2 else None
        comp["latency_diff"] = (comp["latency_2"] or 0) - (comp["latency_1"] or 0)
        t1 = a1["fields"].get("tokens") if a1 else None
        t2 = a2["fields"].get("tokens") if a2 else None
        comp["tokens_1"] = t1
        comp["tokens_2"] = t2
        comp["tokens_diff"] = ((t2 or 0) - (t1 or 0)) if t1 is not None or t2 is not None else None
        comp["error_1"] = a1["error"] if a1 else None
        comp["error_2"] = a2["error"] if a2 else None

        if comp["answer_changed"]:
            sm = SequenceMatcher(None, ans1.split(), ans2.split())
            diff_ops = []
            for op, i1, i2, j1, j2 in sm.get_opcodes():
                if op == "equal":
                    diff_ops.append(("equal", " ".join(ans1.split()[i1:i2])))
                elif op == "delete":
                    diff_ops.append(("delete", " ".join(ans1.split()[i1:i2])))
                elif op == "insert":
                    diff_ops.append(("insert", " ".join(ans2.split()[j1:j2])))
                elif op == "replace":
                    diff_ops.append(("delete", " ".join(ans1.split()[i1:i2])))
                    diff_ops.append(("insert", " ".join(ans2.split()[j1:j2])))
            comp["diff_ops"] = diff_ops

        comparisons.append(comp)

    diff_result = {
        "run_1": {"run_id": d1["run_id"], "run_number": d1["run_number"], "version": d1.get("version")},
        "run_2": {"run_id": d2["run_id"], "run_number": d2["run_number"], "version": d2.get("version")},
        "summary": {
            "total": len(comparisons),
            "changed": sum(1 for c in comparisons if c["answer_changed"]),
            "avg_latency_diff": int(sum(c["latency_diff"] for c in comparisons) / len(comparisons)) if comparisons else 0,
        },
        "comparisons": comparisons,
    }

    if as_json:
        click.echo(json.dumps(diff_result, indent=2, default=str))
        return

    click.echo(f"Comparing run {d1['run_id']} vs {d2['run_id']}")
    click.echo(f"Changed: {diff_result['summary']['changed']}/{diff_result['summary']['total']} questions")
    click.echo(f"Avg latency diff: {diff_result['summary']['avg_latency_diff']:+d}ms")
    click.echo("")

    for comp in comparisons:
        marker = "*" if comp["answer_changed"] else " "
        click.echo(f"{marker} Q: {comp['question']}")
        lat1 = f"{comp['latency_1']}ms" if comp['latency_1'] is not None else "n/a"
        lat2 = f"{comp['latency_2']}ms" if comp['latency_2'] is not None else "n/a"
        click.echo(f"  Latency: {lat1} -> {lat2} ({comp['latency_diff']:+d}ms)")
        if comp.get("tokens_diff") is not None:
            click.echo(f"  Tokens:  {comp['tokens_1']} -> {comp['tokens_2']} ({comp['tokens_diff']:+d})")
        if comp["error_1"] or comp["error_2"]:
            if comp["error_1"]:
                click.echo(f"  Error (run 1): {comp['error_1']}")
            if comp["error_2"]:
                click.echo(f"  Error (run 2): {comp['error_2']}")
        if comp["answer_changed"] and "diff_ops" in comp:
            parts = []
            for op, text in comp["diff_ops"]:
                if op == "equal":
                    parts.append(text)
                elif op == "delete":
                    parts.append(f"[-{text}-]")
                elif op == "insert":
                    parts.append(f"[+{text}+]")
            click.echo(f"  Diff: {' '.join(parts)}")
        click.echo("")


@cli.command()
@click.option("--eval-dir", default=".eval", type=click.Path(), help="Eval output directory")
@click.option("--config", "config_path", default="eval.yaml", type=click.Path(), help="Path to eval config file")
@click.option("--output", default=None, type=click.Path(), help="Output HTML path")
@click.option("--template", default=None, type=click.Path(), help="Path to Jinja2 HTML template")
@click.option("--open", "open_browser", is_flag=True, help="Open report in browser")
def report(eval_dir: str, config_path: str, output: str | None, template: str | None, open_browser: bool):
    """Generate HTML report."""
    from jinja2 import Template

    runs_dir = Path(eval_dir) / "runs"
    index = load_index(runs_dir)
    if not index["runs"]:
        raise click.ClickException("No runs found")

    all_runs = []
    for meta in sorted(index["runs"], key=lambda r: r["run_number"]):
        run_file = runs_dir / f"run_{meta['run_id']}.json"
        if run_file.exists():
            all_runs.append(json.loads(run_file.read_text()))

    template_path = None
    if template:
        template_path = Path(template)
    else:
        default = Path(__file__).parent / "report_template.html"
        if default.exists():
            template_path = default

    if template_path and template_path.exists():
        tmpl = Template(template_path.read_text())
    else:
        tmpl = Template(DEFAULT_REPORT_TEMPLATE)

    output_path = Path(output) if output else Path(eval_dir) / "report.html"
    html = tmpl.render(runs=all_runs, index=index, generated_at=datetime.now().isoformat())
    output_path.write_text(html)
    click.echo(f"Report saved to {output_path}")

    if open_browser:
        webbrowser.open(f"file://{output_path.resolve()}")


# ---------------------------------------------------------------------------
# Default HTML template
# ---------------------------------------------------------------------------

DEFAULT_REPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Eval Report</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 2rem; color: #333; }
  h1 { border-bottom: 2px solid #333; padding-bottom: 0.5rem; }
  h2 { margin-top: 2rem; color: #555; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
  th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
  th { background: #f5f5f5; }
  tr:nth-child(even) { background: #fafafa; }
  .pass { color: #2a7; }
  .fail { color: #c33; }
  .meta { color: #888; font-size: 0.85em; }
  .answer { max-width: 600px; white-space: pre-wrap; word-break: break-word; }
</style>
</head>
<body>
<h1>Eval Report</h1>
<p class="meta">Generated: {{ generated_at }}</p>

<h2>Summary</h2>
<table>
<tr><th>Run</th><th>Version</th><th>Target</th><th>Passed</th><th>Failed</th><th>Avg Latency</th><th>Tokens</th><th>Timestamp</th></tr>
{% for run in runs %}
<tr>
  <td>{{ run.run_id }}</td>
  <td>{{ run.version or "-" }}</td>
  <td>{{ run.target }}</td>
  <td class="pass">{{ run.summary.passed }}</td>
  <td class="fail">{{ run.summary.failed }}</td>
  <td>{{ run.summary.avg_latency_ms }}ms</td>
  <td>{{ run.summary.total_tokens }}</td>
  <td class="meta">{{ run.timestamp }}</td>
</tr>
{% endfor %}
</table>

{% for run in runs %}
<h2>Run {{ run.run_id }}</h2>
<p class="meta">{{ run.target }} ({{ run.target_type }}) &mdash; {{ run.git_branch }}@{{ run.git_hash }}</p>
<table>
<tr><th>#</th><th>Question</th><th>Answer</th><th>Latency</th><th>Error</th></tr>
{% for r in run.results %}
<tr>
  <td>{{ r.index + 1 }}</td>
  <td>{{ r.question }}</td>
  <td class="answer">{{ r.answer or "-" }}</td>
  <td>{{ r.latency_ms }}ms</td>
  <td class="{% if r.error %}fail{% endif %}">{{ r.error or "-" }}</td>
</tr>
{% endfor %}
</table>
{% endfor %}

</body>
</html>
"""


if __name__ == "__main__":
    cli()
