from __future__ import annotations

from the_evaluator.engine.types import (
    DiagnosticLocation,
    ReportDescriptor,
    RuleCategory,
    RuleContext,
    RuleMeta,
    Severity,
    TargetType,
)

MAX_LINES = 300


class ClaudeMdLineCount:
    meta = RuleMeta(
        id="claude-md/line-count",
        default_severity=Severity.WARNING,
        fixable=False,
        description="CLAUDE.md should be under 300 lines — bloated files cause Claude to ignore instructions",
        category=RuleCategory.CONTENT,
        messages={
            "too_long": "CLAUDE.md is {{lines}} lines — recommended maximum is 300. Bloated files cause Claude to ignore your actual instructions.",
        },
        target_type=TargetType.CLAUDE_MD,
    )

    def create(self, context: RuleContext) -> None:
        cmd = context.claude_md
        if cmd is None:
            return

        if cmd.line_count > MAX_LINES:
            context.report(ReportDescriptor(
                message_id="too_long",
                data={"lines": str(cmd.line_count)},
                location=DiagnosticLocation(file=cmd.file_path, start_line=1),
            ))
