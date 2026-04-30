from the_evaluator.engine.registry import register_rule


def register_all_rules() -> None:
    """Import and register all built-in rules."""
    from the_evaluator.rules.structural.skill_md_exists import SkillMdExists
    from the_evaluator.rules.frontmatter.description_required import DescriptionRequired
    from the_evaluator.rules.frontmatter.trigger_quality import TriggerQuality
    from the_evaluator.rules.frontmatter.format_valid import FormatValid
    from the_evaluator.rules.content.token_budget import TokenBudget
    from the_evaluator.rules.content.broken_references import BrokenReferences
    from the_evaluator.rules.content.duplicate_detection import DuplicateDetection
    from the_evaluator.rules.security.no_prompt_injection import NoPromptInjection
    from the_evaluator.rules.security.no_credential_access import NoCredentialAccess

    for rule_cls in [
        SkillMdExists,
        DescriptionRequired,
        TriggerQuality,
        FormatValid,
        TokenBudget,
        BrokenReferences,
        DuplicateDetection,
        NoPromptInjection,
        NoCredentialAccess,
    ]:
        register_rule(rule_cls())
