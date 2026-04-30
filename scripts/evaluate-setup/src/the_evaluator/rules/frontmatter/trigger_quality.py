from __future__ import annotations



from the_evaluator.engine.types import (
    DiagnosticFix,
    DiagnosticLocation,
    ReportDescriptor,
    RuleCategory,
    RuleContext,
    RuleMeta,
    Severity,
)



class TriggerQuality:
    meta: RuleMeta = RuleMeta(
        id="frontmatter/trigger-quality",
        default_severity=Severity.WARNING,
        fixable=True,
        description="Description should start with 'Use when' for Claude Search Optimization",
        category=RuleCategory.FRONTMATTER,
        messages={
            "missing_prefix": (
                "Description does not start with 'Use when' — "
                "this hurts Claude Code's ability to activate the skill at the right time"
            ),
        },
    )

    def create(self, context: RuleContext) -> None:
        skill = context.skill
        if skill.parse_errors:
            return

        description = skill.frontmatter.get("description", "")
        if not isinstance(description, str) or not description:
            return

        if not description.lower().startswith("use when"):
            fixed = f"Use when {description[0].lower()}{description[1:]}"
            context.report(
                ReportDescriptor(
                    message_id="missing_prefix",
                    location=DiagnosticLocation(
                        file=skill.skill_md_path,
                        start_line=skill.frontmatter_start_line or 1,
                    ),
                    fix=DiagnosticFix(
                        description='Add "Use when" prefix to description',
                        replacement=f'description: "{fixed}"',
                    ),
                )
            )
