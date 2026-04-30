from __future__ import annotations



from the_evaluator.engine.types import (
    DiagnosticLocation,
    ReportDescriptor,
    RuleCategory,
    RuleContext,
    RuleMeta,
    Severity,
)

SIMILARITY_THRESHOLD = 0.85

_all_skill_texts: dict[str, str] = {}
_duplicates_reported: set[tuple[str, str]] = set()


def reset_duplicate_state() -> None:
    _all_skill_texts.clear()
    _duplicates_reported.clear()


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)



class DuplicateDetection:
    meta: RuleMeta = RuleMeta(
        id="content/duplicate-detection",
        default_severity=Severity.WARNING,
        fixable=False,
        description="Detect near-duplicate skills",
        category=RuleCategory.CONTENT,
        messages={
            "duplicate": "{{similarity}}% similar to '{{other}}' — consider merging",
        },
    )

    def create(self, context: RuleContext) -> None:
        skill = context.skill
        if not skill.body:
            return

        skill_key = skill.dir_name
        _all_skill_texts[skill_key] = skill.body

        for other_name, other_text in _all_skill_texts.items():
            if other_name == skill_key:
                continue

            pair = tuple(sorted([skill_key, other_name]))
            if pair in _duplicates_reported:
                continue

            similarity = _jaccard_similarity(skill.body, other_text)
            if similarity >= SIMILARITY_THRESHOLD:
                _duplicates_reported.add(pair)
                context.report(
                    ReportDescriptor(
                        message_id="duplicate",
                        data={
                            "similarity": str(int(similarity * 100)),
                            "other": other_name,
                        },
                        location=DiagnosticLocation(
                            file=skill.skill_md_path,
                            start_line=1,
                        ),
                    )
                )
