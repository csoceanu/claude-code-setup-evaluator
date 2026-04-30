from the_evaluator.config.presets.recommended import RECOMMENDED
from the_evaluator.config.presets.strict import STRICT
from the_evaluator.config.presets.security import SECURITY

PRESETS: dict[str, dict[str, str]] = {
    "recommended": RECOMMENDED,
    "strict": STRICT,
    "security": SECURITY,
}

__all__ = ["PRESETS", "RECOMMENDED", "STRICT", "SECURITY"]
