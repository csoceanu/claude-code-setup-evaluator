from __future__ import annotations

import re
from pathlib import Path

import tiktoken
import yaml

from the_evaluator.engine.registry import get_all_rules
from the_evaluator.engine.suppression import is_suppressed, parse_suppressions
from the_evaluator.engine.types import (
    Diagnostic,
    DiagnosticLocation,
    LintResult,
    ParsedSkill,
    ReportDescriptor,
    RuleContext,
    Severity,
)

_INTERPOLATION_RE = re.compile(r"\{\{(\w+)\}\}")

try:
    _ENCODER = tiktoken.encoding_for_model("claude-sonnet-4-20250514")
except Exception:
    _ENCODER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def _interpolate(template: str, data: dict[str, str | int] | None) -> str:
    if not data:
        return template
    return _INTERPOLATION_RE.sub(
        lambda m: str(data.get(m.group(1), m.group(0))), template
    )


def parse_skill(skill_path: str) -> ParsedSkill:
    """Parse a skill directory or SKILL.md file into a ParsedSkill."""
    path = Path(skill_path)
    parse_errors: list[str] = []

    if path.is_file() and path.name.lower() == "skill.md":
        skill_dir = path.parent
        skill_md = path
    elif path.is_dir():
        skill_dir = path
        candidates = [p for p in path.iterdir() if p.name.lower() == "skill.md"]
        if candidates:
            skill_md = candidates[0]
        else:
            return ParsedSkill(
                dir_path=str(skill_dir),
                dir_name=skill_dir.name,
                skill_md_path=str(skill_dir / "SKILL.md"),
                raw_content="",
                frontmatter={},
                raw_frontmatter="",
                frontmatter_start_line=0,
                body="",
                body_start_line=0,
                files=_list_files(skill_dir),
                parse_errors=["SKILL.md not found"],
            )
    else:
        return ParsedSkill(
            dir_path=str(path),
            dir_name=path.name,
            skill_md_path=str(path),
            raw_content="",
            frontmatter={},
            raw_frontmatter="",
            frontmatter_start_line=0,
            body="",
            body_start_line=0,
            files=[],
            parse_errors=[f"Path does not exist: {path}"],
        )

    raw_content = skill_md.read_text()

    frontmatter: dict = {}
    raw_frontmatter = ""
    frontmatter_start_line = 0
    body = raw_content
    body_start_line = 1

    lines = raw_content.split("\n")
    if lines and lines[0].strip() == "---":
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break

        if end_idx is not None:
            frontmatter_start_line = 1
            raw_frontmatter = "\n".join(lines[1:end_idx])
            body = "\n".join(lines[end_idx + 1 :])
            body_start_line = end_idx + 2

            try:
                parsed = yaml.safe_load(raw_frontmatter)
                if isinstance(parsed, dict):
                    frontmatter = parsed
                else:
                    parse_errors.append("Frontmatter is not a YAML mapping")
            except yaml.YAMLError as e:
                parse_errors.append(f"YAML parse error: {e}")
        else:
            parse_errors.append("Frontmatter opening '---' found but no closing '---'")

    tokens = _count_tokens(raw_content)

    return ParsedSkill(
        dir_path=str(skill_dir),
        dir_name=skill_dir.name,
        skill_md_path=str(skill_md),
        raw_content=raw_content,
        frontmatter=frontmatter,
        raw_frontmatter=raw_frontmatter,
        frontmatter_start_line=frontmatter_start_line,
        body=body,
        body_start_line=body_start_line,
        files=_list_files(skill_dir),
        parse_errors=parse_errors,
        tokens=tokens,
    )


def _list_files(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(
        str(p.relative_to(directory))
        for p in directory.rglob("*")
        if p.is_file() and ".git" not in p.parts
    )


def lint(skill_path: str, config_rules: dict[str, str | list] | None = None) -> LintResult:
    """Lint a single skill directory or SKILL.md file."""
    skill = parse_skill(skill_path)
    diagnostics: list[Diagnostic] = []
    suppression_count = 0

    suppressions = parse_suppressions(skill.raw_content) if skill.raw_content else {}

    for parse_error in skill.parse_errors:
        diagnostics.append(
            Diagnostic(
                rule_id="parser",
                severity=Severity.ERROR,
                message=parse_error,
                location=DiagnosticLocation(file=skill.skill_md_path),
                category=skill.parse_errors[0] if skill.parse_errors else "structural",
            )
        )

    rules = get_all_rules()
    config_rules = config_rules or {}

    for rule in rules:
        severity_config = config_rules.get(rule.meta.id)

        if severity_config == "off":
            continue

        if isinstance(severity_config, list) and len(severity_config) > 0:
            sev_str = severity_config[0]
            options = severity_config[1:]
        elif isinstance(severity_config, str):
            sev_str = severity_config
            options = []
        else:
            sev_str = rule.meta.default_severity.value
            options = []

        if sev_str == "off":
            continue

        try:
            severity = Severity(sev_str)
        except ValueError:
            severity = rule.meta.default_severity

        def make_report(
            rule_id: str,
            sev: Severity,
            meta_messages: dict[str, str],
            category: str,
            fixable: bool,
            file_path: str,
        ):
            def report(descriptor: ReportDescriptor) -> None:
                nonlocal suppression_count
                loc = descriptor.location or DiagnosticLocation(file=file_path)
                if is_suppressed(suppressions, rule_id, loc.start_line):
                    suppression_count += 1
                    return

                template = meta_messages.get(descriptor.message_id, descriptor.message_id)
                message = _interpolate(template, descriptor.data)
                effective_severity = descriptor.severity_override or sev

                diagnostics.append(
                    Diagnostic(
                        rule_id=rule_id,
                        severity=effective_severity,
                        message=message,
                        location=loc,
                        category=category,
                        fix=descriptor.fix if fixable else None,
                    )
                )

            return report

        context = RuleContext(
            skill=skill,
            report=make_report(
                rule.meta.id,
                severity,
                rule.meta.messages,
                rule.meta.category,
                rule.meta.fixable,
                skill.skill_md_path,
            ),
            severity=severity,
            options=options,
        )

        rule.create(context)

    return LintResult(
        skill_path=skill_path,
        skill_name=skill.dir_name,
        tokens=skill.tokens,
        diagnostics=diagnostics,
        error_count=sum(1 for d in diagnostics if d.severity == Severity.ERROR),
        warning_count=sum(1 for d in diagnostics if d.severity == Severity.WARNING),
        info_count=sum(1 for d in diagnostics if d.severity == Severity.INFO),
        fixable_count=sum(1 for d in diagnostics if d.fix is not None),
        suppression_count=suppression_count,
    )


def lint_directory(
    scan_path: str, config_rules: dict[str, str | list] | None = None
) -> list[LintResult]:
    """Lint all skills found under a directory."""
    path = Path(scan_path)
    results = []

    if path.is_file() and path.name.lower() == "skill.md":
        results.append(lint(str(path.parent), config_rules))
        return results

    if not path.is_dir():
        return results

    skill_dirs: list[Path] = []
    for p in sorted(path.rglob("SKILL.md")):
        if ".git" not in p.parts:
            skill_dirs.append(p.parent)

    if not skill_dirs and (path / "SKILL.md").exists():
        skill_dirs = [path]

    seen: set[str] = set()
    for skill_dir in skill_dirs:
        resolved = str(skill_dir.resolve())
        if resolved not in seen:
            seen.add(resolved)
            results.append(lint(str(skill_dir), config_rules))

    return results
