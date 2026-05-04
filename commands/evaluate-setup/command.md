---
description: "Evaluate your Claude Code setup — skills, commands, CLAUDE.md. Identifies what to keep, remove, merge, and fix."
---

# /evaluate-setup

You are running **the-evaluator** — a health check for Claude Code setups. You will evaluate skills, commands, and CLAUDE.md files, then produce a report with verdicts and recommendations.

## Hard Rules

1. **Never give a verdict without running the rubric.** You MUST read the actual file content and score all rubric dimensions before assigning a star rating or verdict. Layer 1 error/warning counts are input data, not the verdict — a file with 10 false-positive warnings can still be ★★★★★.
2. **Every item must have a full rubric score block.** If a rubric score block is missing for any evaluated item, the review is incomplete. Every skill, command, CLAUDE.md, and hook MUST have all dimensions scored with one-sentence justifications before the verdict line. No exceptions, no shortcuts.
3. **Read before you judge.** Do not summarize an item based on Layer 1 output alone. You must read the actual file content to evaluate quality, clarity, and redundancy. Layer 1 catches mechanical issues. Layer 2 catches everything else.
4. **Don't manufacture problems.** If the setup is good, say so. Not every run needs to produce a list of changes. A healthy setup with minor cosmetic issues should get a clear "your setup is solid" verdict — not a long list of suggestions that creates unnecessary work. Only recommend changes that would make a real difference. "You could trim 50 tokens from this skill" is not a real recommendation. "This skill duplicates another and wastes 1,000 tokens every session" is.
5. **Always end with a short summary.** Regardless of output format, the last thing the user sees in the terminal must be a short summary (see Step 5b). The full review is either above in the terminal or saved to a file — the summary tells the user the bottom line and where to find details.

## Step 0: Ask the User Before Starting

Before running anything, ask the user two questions using AskUserQuestion:

1. **Output format:** "Where do you want the full review?"
   - **Terminal** — print everything here (can be long)
   - **File** — save to `evaluate-setup-report.md` in the project root (recommended for full setup scans)

2. **Scope:** "What do you want to evaluate?"
   - **Everything** — skills + commands + CLAUDE.md + hooks
   - **Skills only**
   - **A specific item** — ask which one

Wait for answers before proceeding. The user's choices determine where output goes and what gets scanned.

## Arguments

`$ARGUMENTS` may include:
- A path (e.g., `~/.claude/skills/`, `skills/python-conventions/`)
- `--preset strict` or `--preset security` (default: recommended)
- `--deep` (run Layer 3 A/B evaluation — requires API keys)
- `--deep --red-team` (adversarial testing for preventive skills)
- Natural language like "evaluate my setup", "is my python skill any good?"

If no path is given and the user didn't answer Step 0 (e.g., they passed arguments directly), default to scanning skills in the current directory with terminal output.

## Step 1: Run Layer 1 (Static Analysis)

Find the static analyzer script relative to this command:

```bash
SCRIPT_DIR="$(dirname "$(readlink -f commands/evaluate-setup/command.md 2>/dev/null || echo commands/evaluate-setup/command.md)")"
ANALYZER="$(find "$(dirname "$SCRIPT_DIR")" -path '*/evaluate-setup/src/the_evaluator/cli.py' 2>/dev/null | head -1)"
PROJECT_DIR="$(echo "$ANALYZER" | sed 's|/src/the_evaluator/cli.py||')"
```

Run the analysis:

```bash
uv run --project "$PROJECT_DIR" evaluate-setup scan <PATH> [--preset <PRESET>]
```

Read the JSON output. This gives you per-skill diagnostics with rule IDs, severities, and token counts.

## Step 2: Read Actual Files (Layer 2 Preparation)

Read the actual content of:
1. Every skill file (SKILL.md) in the scan path
2. Every command file (command.md) found nearby
3. The user's CLAUDE.md files (project and user level)

You need the actual content — not just the Layer 1 JSON — to evaluate quality, redundancy, and content.

## Step 3: Evaluate Each Skill (Layer 2)

For each skill, produce a **structured rubric score** on 5 dimensions:

### Rubric Dimensions

**Specificity (weight 0.25)**
- 1: Entirely vague platitudes, no actionable instructions
- 2: Mostly generic advice with one or two specific rules
- 3: Mix of specific and generic; some rules change Claude's behavior
- 4: Mostly specific, actionable instructions with concrete patterns
- 5: Every instruction is specific, actionable, includes concrete patterns or examples

**Redundancy (weight 0.25)**
- 1: Every instruction duplicates Claude's default behavior
- 2: 75%+ is default behavior, very little unique value
- 3: Some unique value, but 50%+ is default behavior
- 4: Mostly unique, with minor overlap with Claude's defaults
- 5: Entirely unique — teaches Claude something it genuinely doesn't know

Things Claude already does by default (always redundant):
- "Write clean, readable code"
- "Be helpful and thorough"
- "Handle errors properly" (too vague to add value)
- "Follow best practices"
- "Use proper formatting"
- "Think step by step"
- "Consider edge cases"

A skill is NOT redundant if it provides specific, actionable rules. "Always use `raise from` for exception chaining in Python" is specific enough to change behavior.

**Also check for overlap with Claude's built-in behavior.** Claude already does many things by default (plan mode, code review, commit messages, code explanation). A skill that just wraps a Claude default without adding specific rules or constraints is redundant. Ask: "if I deleted this skill, would Claude behave differently?" If not → redundant.

**Trigger quality (weight 0.20)**
- 1: No description, or description triggers on everything
- 2: Description exists but is too broad or too narrow
- 3: Description is reasonable but could be more precise
- 4: Good description that targets the right tasks most of the time
- 5: Description precisely targets the right tasks; starts with "Use when"; doesn't overlap with other skills

**Token efficiency (weight 0.15)**
- 1: >3,000 tokens with low value density
- 2: 2,000-3,000 tokens, or under 1,500 with very low value
- 3: Under 1,500 tokens, some padding that could be trimmed
- 4: Well-sized, minor optimization possible
- 5: Every token earns its place; high value-to-token ratio

**Content quality (weight 0.15)**
- 1: No structure, no examples, broken references
- 2: Minimal structure, vague instructions
- 3: Decent structure, some examples, no broken references
- 4: Well-organized with examples and clear sections
- 5: Well-organized, includes examples, references valid files, covers edge cases

### Scoring

- Score each dimension 1-5
- Include a **one-sentence justification** for each score citing specific evidence
- Calculate overall: `round(specificity*0.25 + redundancy*0.25 + trigger*0.20 + efficiency*0.15 + quality*0.15)`
- Assign verdict: **KEEP** (4-5 stars), **REVIEW** (3 stars), **REMOVE** (1-2 stars)

### Per-Skill Output Format

```
### skill-name                               ★★★★    KEEP
  Tokens: 663

  Rubric:
    Specificity:      5/5  Concrete rules: raise from, exception hierarchies
    Redundancy:       4/5  One rule overlaps Claude's default
    Trigger quality:  5/5  Targets Python error handling precisely
    Token efficiency: 5/5  663 tokens, high value density
    Content quality:  4/5  Well-structured but could add examples

  + What's good (bullet points)
  ! What could improve (bullet points)
  x What's broken (from Layer 1 diagnostics)
```

## Step 3b: Evaluate CLAUDE.md (if --claude-md or --all)

Score CLAUDE.md on 5 dimensions:

| Dimension | Weight | What to check |
|---|---|---|
| **Conciseness** | 0.25 | Under ~300 lines? Can each line pass "would removing this cause mistakes?" |
| **Signal-to-noise** | 0.25 | Only contains things Claude can't figure out from code? No generic advice? |
| **Skill separation** | 0.20 | Domain-specific rules are in skills (on-demand), not CLAUDE.md (every session)? |
| **Structure** | 0.15 | Clear sections? Critical rules marked? Scannable? |
| **Conflict-free** | 0.15 | No contradictions with any skill? |

## Step 3c: Evaluate Commands (if --commands or --all)

Score each command on 7 dimensions:

| Dimension | Weight | What to check |
|---|---|---|
| **Description quality** | 0.20 | Clear, concise description for the UI menu? |
| **Instruction clarity** | 0.20 | Claude knows exactly what to do, in what order? |
| **Script integrity** | 0.15 | Referenced scripts exist? Discovery pattern works? |
| **Scope appropriateness** | 0.10 | Should this be a command (user-triggered) or a skill (auto-triggered)? |
| **Token efficiency** | 0.10 | Concise or bloated? |
| **Redundancy with defaults** | 0.15 | Does Claude already do this without the command? Claude has built-in plan mode, generates commit messages, explains code, and reviews code by default. A command is only justified if it adds specific rules, constraints, or structure that Claude wouldn't follow unprompted. Ask: "if I deleted this command, could I get the same result by just asking Claude?" If yes → redundant. |
| **Robustness** | 0.10 | Does the command handle edge cases? Does it hardcode assumptions (specific tools, languages, thresholds) that should be detected from the project? Does it depend on skills loading reliably? Does it gracefully handle missing dependencies? |

## Step 3d: Evaluate Hooks (if --hooks or --all)

For each hook, check:
- Does the hook have a clear purpose?
- Does the referenced script/command exist?
- Are there dangerous patterns (rm -rf, force push)?
- Is this the right mechanism? (hooks are deterministic — 100% execution. If the behavior is advisory, it should be in CLAUDE.md or a skill instead.)

## Step 4: Cross-Type Optimization (the full picture)

This is where you look at the **whole setup** and suggest transformations between types. Only suggest transformations when you genuinely believe they would improve the setup — don't suggest changes for the sake of it.

### Transformation types to consider:

**Skill → Hook** — If a skill contains rules that MUST happen every time without exception (e.g., "always run linting after editing"), that's a hook, not a skill. Skills are advisory (~80% adherence). Hooks are deterministic (100%). Ask: "If Claude ignores this instruction, would something break?" If yes → hook.

**Skill → Command** — If a skill describes a specific workflow the user triggers explicitly (e.g., "audit my code", "generate a migration", "deploy to staging"), it should be a command. Skills are for passive behavior ("whenever you write Python, do X"). Commands are for active actions the user invokes with `/command-name`.

**Command → Skill** — If a command describes general behavior that should always be active (e.g., a `/python-style` command that the user runs every time), it should be a skill that auto-triggers.

**Skill content → CLAUDE.md** — If a skill contains rules that apply to EVERY conversation regardless of task (e.g., "always use uv for Python", "never commit .env files"), those belong in CLAUDE.md. Skills load on-demand; CLAUDE.md loads every session. Universal rules should be in CLAUDE.md.

**CLAUDE.md content → Skill** — The reverse. If CLAUDE.md contains domain-specific rules that only matter sometimes (e.g., "when writing data pipelines, use this stage structure"), those waste context in every session. Move them to a skill that loads only when relevant.

**CLAUDE.md content → Hook** — If CLAUDE.md says "always run tests before committing" but Claude sometimes forgets — make it a hook. The hook guarantees it happens.

### Setup-wide checks:

- **Merge candidates**: Skills covering related topics that would be stronger combined
- **Overlapping triggers**: Skills whose descriptions might cause multiple to load unnecessarily
- **Coverage gaps**: Obvious missing areas based on what's present
- **Total context budget**: Sum all skills + CLAUDE.md + commands tokens, warn if >20% of context window
- **Redundancy across types**: Same instruction appearing in CLAUDE.md AND a skill (double token cost)
- **Conflicts across types**: CLAUDE.md says one thing, a skill says the opposite

### Example transformation suggestions:

```
## Cross-Type Optimization

  ⟳ Skill → Hook: security-check says "always run pre-commit before pushing" —
    this should be a hook to guarantee it runs every time, not a skill that
    Claude might skip.

  ⟳ Skill → Command: brainstorming says "you MUST use this before any creative work" —
    the hard gate makes it behave like a command. Consider making it a /brainstorm
    command instead.

  ⟳ CLAUDE.md → Skill: The "Testing" section in CLAUDE.md (lines 45-60) contains
    pytest-specific rules that only matter when writing tests. Move to a
    testing-conventions skill that loads on demand.

  ✓ No conflicts detected between CLAUDE.md and skills.
  ✓ No redundant content detected across types.
```

## Step 5: Produce the Report

### Step 5a: Full Review

If the user chose **terminal output**, print the full review directly. If they chose **file output**, write it to `evaluate-setup-report.md` in the project root and tell the user where to find it.

Full review format:

```
## Static Analysis (Layer 1)
  Preset: <preset> | <N> skills, <M> commands, <K> other items
  <tokens> tokens total (<pct>% of context budget)
  <errors> errors | <warnings> warnings | <info> info
  <fixable> auto-fixable issues found

## Per-Item Review (Layer 2)

### Skills
  [Per-skill rubric output, one per skill]

### CLAUDE.md (if evaluated)
  [CLAUDE.md rubric output]

### Commands (if evaluated)
  [Per-command rubric output]

### Hooks (if evaluated)
  [Per-hook review]

## Cross-Type Optimization
  [Transformation suggestions — only when genuinely beneficial]

## Setup-Wide Recommendations
  [Merge candidates, overlapping triggers, coverage gaps, context budget]
```

### Step 5b: Terminal Summary (ALWAYS printed, regardless of output format)

This is the last thing the user sees. Keep it short — 10-15 lines max. It tells the user the bottom line.

```
## Evaluation Summary

<Overall verdict — one sentence. E.g., "Your setup is solid" or "Found 2 issues that need attention.">
Reviewed <N> skills, <M> commands, CLAUDE.md. Total: <tokens> tokens (<pct>%).

Suggestions (say "do 1", "do 2", "skip 3" to act on them):
  1. <one-line suggestion>
  2. <one-line suggestion>
  3. <one-line suggestion>

Full review: <"printed above" or "saved to evaluate-setup-report.md">
```

**Numbering rules:**
- Every suggestion gets a number, starting from 1
- Each number is one actionable item Claude can execute if the user says "do N"
- Keep each suggestion to one line — the full explanation is in the detailed review
- If the setup is healthy, it's fine to have just 1-2 suggestions or even zero. Don't pad.

**Key principle:** If nothing significant needs to change, say "your setup is solid" and list only the minor items. Don't pad the summary with nice-to-have suggestions. The user should be able to read the summary in 10 seconds and know: do I need to act or not?

## Step 6: Deep Evaluation (Layer 3 — only if --deep was passed)

If `--deep` was requested:

1. Check that `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` are available in the environment
2. Show estimated cost: 46 API calls per skill × number of skills to test
3. Ask the user for confirmation before proceeding
4. Run `deep_eval.py`:

```bash
uv run --project "$PROJECT_DIR" --extra deep python -m the_evaluator.deep_eval <PATH> [--red-team] [--model sonnet]
```

5. Read the JSON results
6. For each skill tested, add A/B evidence to the report:
   - Standard mode: wins/ties/losses, confidence levels, overall verdict (HELPS/NO IMPACT/HURTS)
   - Red-team mode: held/broke/partial, red-team score, overall verdict (STRONG/WEAK/FRAGILE)

If `--deep` was NOT requested but some skills scored 2 stars or below:
- Suggest: "3 skills scored poorly. Want me to run deep evaluation on those? Requires ANTHROPIC_API_KEY and GEMINI_API_KEY in your .env."
