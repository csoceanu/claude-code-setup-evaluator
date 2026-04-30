from __future__ import annotations



from the_evaluator.engine.types import (
    DiagnosticLocation,
    ReportDescriptor,
    RuleCategory,
    RuleContext,
    RuleMeta,
    Severity,
)

MAX_TOKENS = 1500



class TokenBudget:
    meta: RuleMeta = RuleMeta(
        id="content/token-budget",
        default_severity=Severity.WARNING,
        fixable=False,
        description="Skill content should be under 1,500 tokens",
        category=RuleCategory.CONTENT,
        messages={
            "over_budget": "Skill is {{tokens}} tokens — recommended maximum is 1,500",
        },
    )

    def create(self, context: RuleContext) -> None:
        skill = context.skill
        if skill.tokens > MAX_TOKENS:
            context.report(
                ReportDescriptor(
                    message_id="over_budget",
                    data={"tokens": str(skill.tokens)},
                    location=DiagnosticLocation(
                        file=skill.skill_md_path,
                        start_line=skill.body_start_line or 1,
                    ),
                )
            )
