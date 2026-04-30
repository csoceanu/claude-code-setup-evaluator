from the_evaluator.config.presets.recommended import RECOMMENDED

STRICT: dict[str, str] = {
    **RECOMMENDED,
    "frontmatter/trigger-quality": "error",
    "frontmatter/format-valid": "error",
    "content/token-budget": "error",
}
