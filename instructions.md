# Getting Started with the AI Workspace

Welcome! This workspace gives you superpowers when working with Claude Code. Here's how to get started and what's available to you.

---

## Setup

1. **Clone your repo** into the `repositories/` folder:
   ```bash
   cd repositories/
   git clone <your-repo-url>
   cd ../
   git submodule add <your-repo-url> repositories/<repo-name>
   ```

2. **Start Claude Code** in the workspace root:
   ```bash
   claude
   ```

3. **Type `/toolkit`** to see what's available and get recommendations based on your current repo.

That's it. Everything else activates automatically as you work.

---

## How It Works

This workspace has four types of capabilities:

- **Skills** — knowledge the AI carries. Activate automatically when relevant. You don't do anything.
- **Commands** — buttons you press. Type `/command` to trigger a specific workflow.
- **Agents** — helpers the AI sends to do work in parallel. You don't control them.
- **Hooks** — tripwires that fire on events (like blocking a push if secrets are detected).

---

## Skills (automatic)

Skills activate on their own — you just get better results.

### python-patterns
**What:** Team conventions for credential management with dotenv — `.env` file structure, loading patterns, secure defaults.
**When:** Writing code that uses environment variables or API keys.
**Example:** You write `os.getenv("API_KEY", "AIza...")` — the AI flags the real key in the default value and fixes it to `os.getenv("API_KEY")` with a validation check.

### python-testing
**What:** TDD workflow (red/green/refactor) + pytest patterns + data science testing (DataFrames, models, validation).
**When:** Writing tests, adding features with TDD, improving coverage.
**Example:** You say "add a validation function" — the AI writes a failing test first with `pd.testing.assert_frame_equal` and parametrized edge cases, then implements the function to make it pass.

### security-check
**What:** Scans for credential leaks (10+ API key patterns: Gemini, OpenAI, Jira, AWS, GitHub), insecure code (eval, pickle, shell injection), and LLM-specific risks (PII sent to external APIs, executing LLM output).
**When:** Before commits, when touching `.env` or config files, when sending data to LLMs.
**Example:** You send raw email addresses to Gemini in a prompt — the AI flags PII leakage and suggests sanitizing before sending.

### data-pipeline-patterns
**What:** Pipeline stage design, data validation at boundaries, circuit breakers, checkpoint/resume, and a systematic debugging workflow for pipeline failures.
**When:** Building or debugging data pipeline stages, validating JSON data files.
**Example:** You add a new pipeline step — the AI structures it with input validation, metadata in output, checkpoint every 100 items, and a circuit breaker after 5 consecutive API failures.

### api-client-patterns
**What:** Retry with exponential backoff, rate limiting, response validation, authentication patterns, pagination, and LLM response parsing (stripping markdown fences, handling JSON from Gemini).
**When:** Writing code that calls external APIs (Jira, Gemini, LDAP).
**Example:** You build a Jira API client — the AI adds `timeout=30`, retry for 429/500/502/503 with `Retry-After` header support, and validates the response structure before accessing fields.

### git-workflow
**What:** Team-specific git conventions — GitLab and GitHub workflows, submodule push-before-parent pattern, common submodule pitfalls.
**When:** Committing, pushing, resolving merge conflicts, working with submodules.
**Example:** You push changes in a submodule — the AI pushes the submodule first, then updates the parent reference, following the correct order.

### mcp-patterns
**What:** Building and securing MCP servers — schema-first tool design, authentication, input validation, audit logging, and data science MCP patterns (dataset queries, model serving).
**When:** Building MCP servers, configuring `.mcp.json`, reviewing MCP security.
**Example:** You build an MCP tool for querying datasets — the AI enforces Pydantic input schemas with limits (`max_rows=10000`), adds audit logging, and uses principal-based auth.

### verification-loop
**What:** The unified verification engine. Covers environment checks, type checking, linting, tests, code review (with DS anti-patterns like data leakage and missing seeds), and security scans. The `/verify`, `/review`, and `/quality-gate` commands all invoke different phases of this one skill.
**When:** After implementing a feature, before creating an MR, after refactoring.
**Example:** You say "review my changes" — the AI runs Phase 5 (code review), checks for bare `except` clauses, functions over 50 lines, data leakage, and gives a verdict: APPROVE or REQUEST CHANGES.

### deep-research
**What:** Systematic multi-source research — breaks questions into sub-queries, searches in parallel, synthesizes findings with citations.
**When:** Evaluating technologies, investigating APIs, answering complex technical questions.
**Example:** You ask "what's the best Python library for HTML-to-PDF?" — the AI researches weasyprint, pdfkit, playwright, compares tradeoffs, and recommends one with reasoning.

### codebase-onboarding
**What:** Analyzes unfamiliar codebases through 4 phases — reconnaissance, architecture mapping, convention detection, guide generation.
**When:** First time working in a new repo, onboarding a team member.
**Example:** You open a repo you've never seen — the AI maps the directory structure, identifies entry points, detects testing conventions, and produces a "start here" guide.

### compound-engineering
**What:** Captures reusable patterns from sessions — errors that took multiple attempts to fix, user corrections, workarounds — and saves them as persistent memories for future sessions.
**When:** End of significant sessions, when the AI notices something worth remembering, or when you say "remember this" or `/learn`.
**Example:** You spend 20 minutes debugging a `.gitignore` negation issue — the AI saves "use `dir/*` not `dir/` for negation to work" so it never makes that mistake again. Next session, it already knows.

---

## Commands (you trigger these)

Type the command name in the chat to run it.

### /plan
Plan before you code. Restates requirements, searches the codebase for existing solutions (adopt/extend/build), identifies risks, and creates a step-by-step plan. **Waits for your OK before writing any code.**

### /verify
Does my code work? Runs `verification-loop` phases 1-4 (environment, types, lint, tests). Use **after coding, before review.**

### /review
Is my code good? Runs `verification-loop` phase 5 (code review with DS anti-patterns, security, quality). Produces APPROVE or REQUEST CHANGES. Use **after verify.**

### /quality-gate
Am I safe to push? Runs `verification-loop` phases 1-4 + phase 6 (tests + secret scan + pre-commit). Gives READY TO PUSH or BLOCKED. Use **after review, right before `git push`.**

### /test-coverage
Find untested code. Analyzes coverage, lists files without tests, identifies functions needing tests, and prioritizes what to test first (HIGH: core logic, MEDIUM: utilities, LOW: wrappers).

### /toolkit
What can I do here? Shows all available skills, commands, and agents, then recommends which to use based on your current repo and task. **Start here if you're new.**

### /recap
Summarize the session. Generates a structured update with what changed, why, key decisions, and a copy-pasteable message for standup or Slack.

### /diff-explain
Explain changes in plain language. Groups changes by intent — "the pipeline was split into 3 independent steps" instead of "14 files changed." Use for MR reviews or catching up.

### /visualize
Generate a visual project map. Creates an interactive HTML file with a collapsible file tree, color-coded by language, with file sizes and a breakdown chart.

### /ai-engineer-review
Get a brutally honest review from a principal AI engineer. Assesses architecture, code quality, skills/commands/hooks setup, finds redundancy and gaps, scores readability/maintainability/security, and gives the top 3 prioritized improvements with concrete instructions. Can focus on a specific area (`/ai-engineer-review security`) or a specific repo (`/ai-engineer-review repositories/ai-initiatives-observer`).

---

## Agents (automatic)

The AI spawns these as sub-processes for parallel or specialized work.

- **Explore** — fast codebase search across many files in parallel
- **Plan** — designs implementation strategies for complex changes
- **general-purpose** — handles multi-step research or complex tasks autonomously

---

## Hooks (automatic)

These run in the background on specific events.

- **Session start** — reports git status of all submodules when you start a session
- **Pre-commit secret scan** — blocks `git commit`/`git push` if API keys are detected in tracked files
- **Auto-skill suggestion** — detects what files you're working with and reminds the AI which skills are relevant

---

## Recommended Workflow

```
/plan          →  align on approach, search for existing solutions
                  ↓
(write code)   →  skills activate automatically
                  ↓
/verify        →  does my code work? (tests, outputs)
                  ↓
/review        →  check code quality and security
                  ↓
/quality-gate  →  am I safe to push? (tests + secrets + lint)
                  ↓
git push       →  secret scan hook runs automatically
                  ↓
/recap         →  summarize for standup or stakeholders
```
