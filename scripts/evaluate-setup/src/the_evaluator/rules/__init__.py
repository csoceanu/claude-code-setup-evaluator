from the_evaluator.engine.registry import register_rule


def register_all_rules() -> None:
    """Import and register all built-in rules."""
    # Skill rules
    from the_evaluator.rules.structural.skill_md_exists import SkillMdExists
    from the_evaluator.rules.frontmatter.description_required import DescriptionRequired
    from the_evaluator.rules.frontmatter.trigger_quality import TriggerQuality
    from the_evaluator.rules.frontmatter.format_valid import FormatValid
    from the_evaluator.rules.content.token_budget import TokenBudget
    from the_evaluator.rules.content.broken_references import BrokenReferences
    from the_evaluator.rules.content.duplicate_detection import DuplicateDetection
    from the_evaluator.rules.security.no_prompt_injection import NoPromptInjection
    from the_evaluator.rules.security.no_credential_access import NoCredentialAccess

    # Command rules
    from the_evaluator.rules.commands.description_required import CommandDescriptionRequired
    from the_evaluator.rules.commands.script_exists import CommandScriptExists

    # CLAUDE.md rules
    from the_evaluator.rules.claude_md.line_count import ClaudeMdLineCount
    from the_evaluator.rules.claude_md.generic_advice import ClaudeMdGenericAdvice
    from the_evaluator.rules.claude_md.skill_duplication import ClaudeMdSkillDuplication

    # Hooks rules
    from the_evaluator.rules.hooks.valid_structure import HooksValidStructure

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
        CommandDescriptionRequired,
        CommandScriptExists,
        ClaudeMdLineCount,
        ClaudeMdGenericAdvice,
        ClaudeMdSkillDuplication,
        HooksValidStructure,
    ]:
        register_rule(rule_cls())
