from __future__ import annotations

import re

from the_evaluator.engine.types import (
    DiagnosticLocation,
    ReportDescriptor,
    RuleCategory,
    RuleContext,
    RuleMeta,
    Severity,
    TargetType,
)

_GENERIC_PATTERNS = [
    (re.compile(r"\bwrite clean code\b", re.I), "write clean code"),
    (re.compile(r"\bbe helpful\b", re.I), "be helpful"),
    (re.compile(r"\bfollow best practices\b", re.I), "follow best practices"),
    (re.compile(r"\buse proper formatting\b", re.I), "use proper formatting"),
    (re.compile(r"\bthink step by step\b", re.I), "think step by step"),
    (re.compile(r"\bconsider edge cases\b", re.I), "consider edge cases"),
    (re.compile(r"\bbe thorough\b", re.I), "be thorough"),
    (re.compile(r"\bhandle errors properly\b", re.I), "handle errors properly"),
    (re.compile(r"\bwrite tests\b(?! for| that| using| with)", re.I), "write tests"),
    (re.compile(r"\buse meaningful (?:variable )?names\b", re.I), "use meaningful names"),
]


class ClaudeMdGenericAdvice:
    meta = RuleMeta(
        id="claude-md/generic-advice",
        default_severity=Severity.INFO,
        fixable=False,
        description="CLAUDE.md should not contain generic advice Claude already follows by default",
        category=RuleCategory.CONTENT,
        messages={
            "generic": "'{{phrase}}' at line {{line}} — Claude already does this by default. Remove it to reduce noise.",
        },
        target_type=TargetType.CLAUDE_MD,
    )

    def create(self, context: RuleContext) -> None:
        cmd = context.claude_md
        if cmd is None:
            return

        lines = cmd.raw_content.split("\n")
        for i, line in enumerate(lines):
            for pattern, phrase in _GENERIC_PATTERNS:
                if pattern.search(line):
                    context.report(ReportDescriptor(
                        message_id="generic",
                        data={"phrase": phrase, "line": str(i + 1)},
                        location=DiagnosticLocation(file=cmd.file_path, start_line=i + 1),
                    ))
                    break
