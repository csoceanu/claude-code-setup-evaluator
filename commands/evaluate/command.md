---
description: "Run evaluation questions against your AI bot/agent and compare results across versions. Supports auto-discovery of bot entry points."
---

# Evaluate Command

Run structured evaluations against AI bots, chatbots, and LLM-powered endpoints. Track how answers change across code versions.

## Arguments

$ARGUMENTS — optional. Can be:
- Empty → run evaluation with existing eval.yaml config
- `--version "label"` → run with a version label
- `report` → generate and open HTML report
- `diff` → compare last two runs
- `diff N M` → compare specific runs
- `list` → show all previous runs
- A quoted question → ad-hoc single question test (not saved as formal run)
- Setup instructions like "look at my code" or "I have endpoints"

## Instructions

### Step 0: Locate the runner script

The evaluation runner script is at the path of THIS command file's sibling:

```bash
# Find the runner script (same directory as this command.md)
RUNNER_SCRIPT="$(dirname "$(readlink -f commands/evaluate/command.md 2>/dev/null || echo commands/evaluate/command.md)")/runner.py"
# If that fails, search for it
[ -f "$RUNNER_SCRIPT" ] || RUNNER_SCRIPT="$(find . -path '*/commands/evaluate/runner.py' -o -path '*/evaluate/runner.py' 2>/dev/null | head -1)"
```

Store this path — you'll use it for all `uv run` calls.

### Step 1: Check if eval.yaml exists

```bash
ls eval.yaml 2>/dev/null
```

**If eval.yaml exists → go to Step 3** (run evaluation).

**If eval.yaml does NOT exist → go to Step 2** (setup).

### Step 2: Setup — help user create eval.yaml

This is the most important step. Be conversational and helpful.

**If the user gave clear instructions** (e.g., "my function is bot.ask" or "endpoint at localhost:8000"):
- Create eval.yaml directly based on what they said
- Ask for questions if not provided

**If the user is vague** (e.g., "look at my code", "I have several endpoints", "figure it out"):
- Scan the codebase to discover entry points:

```bash
# Look for FastAPI/Flask/Django routes
grep -r "app\.\(post\|get\|route\)" --include="*.py" -l .
grep -r "@app\." --include="*.py" -n . | head -20

# Look for common bot function patterns
grep -rn "def \(ask\|chat\|query\|invoke\|respond\|answer\|generate\|handle\)" --include="*.py" . | head -20

# Look for LangChain/LlamaIndex patterns
grep -rn "agent\.\(invoke\|run\|call\)" --include="*.py" . | head -10
grep -rn "chain\.\(invoke\|run\|call\)" --include="*.py" . | head -10

# Look for main entry points
grep -rn "if __name__" --include="*.py" . | head -10

# Look for test files with example questions
find . -name "test_*" -o -name "*_test.py" | head -10

# Check project structure and framework
cat pyproject.toml 2>/dev/null | head -30
cat requirements.txt 2>/dev/null
ls *.py app/ src/ bot/ agent/ 2>/dev/null
```

- Present what you found clearly: "I found 3 endpoints in app/routes.py: POST /chat, POST /support, POST /summarize"
- Ask the user which ones to evaluate
- Read relevant source files to understand the interface (request/response format)

**Suggest questions:**
- If the user doesn't provide questions, look for clues:
  - Test files with example inputs
  - README with usage examples
  - Prompt templates that reveal what the bot does
  - Mock data or fixtures
- Suggest 5-8 questions that cover the bot's domain
- Always let the user modify the list

**Create eval.yaml:**
- Write the file using the appropriate target mode (module/command/endpoint)
- Use auto-start if the bot is a web app that isn't running
- Include field mappings based on the response structure you discovered
- Inform the user: "Created eval.yaml — you can edit it anytime to add questions or change settings."

**eval.yaml format — single target:**
```yaml
target:
  module: "bot.core.ask"        # Python function
  # command: "python bot.py --question '{question}'"  # Shell command
  # endpoint: "http://localhost:8000/ask"  # HTTP endpoint
  # request_field: "question"   # for endpoint mode
  # start_command: "uvicorn app.main:app --port 8000"  # auto-start
  # start_wait: 5

fields:
  answer: "answer"
  # version: "version"
  # tokens: "tokens"

questions:
  - "What is your return policy?"
  - "How do I reset my password?"

# questions_file: "eval_questions.txt"   # alternative: load from file
```

**eval.yaml format — multiple targets:**
```yaml
targets:
  chat-endpoint:
    endpoint: "http://localhost:8000/chat"
    request_field: "message"
    fields:
      answer: "response"
    questions:
      - "What is your return policy?"

  support-bot:
    module: "bots.support.handle"
    fields:
      answer: "answer"
    questions:
      - "My order is late"

settings:
  timeout: 30
  start_command: "uvicorn app.main:app --port 8000"
  start_wait: 3
  stop_command: "kill %1"
```

### Step 3: Run evaluation

Parse the arguments to determine what to do:

**Default (no args or `--version`):** Run the evaluation.

```bash
uv run "$RUNNER_SCRIPT" run --config eval.yaml [--version "label"]
```

The script outputs JSON to stdout and progress to stderr. Parse the JSON output to present results.

**Present results as a formatted table:**

```
Results — N/M passed:
#  Question                              Latency  Tokens  Status
1  "What is your return policy?"          1.2s     340     ✓
2  "How do I reset my password?"          0.8s     210     ✓
3  "What payment methods do you accept?"  ERROR    —       ✗

Avg latency: 1.0s | Total tokens: 550
Saved: .eval/runs/run_001.json
```

**After showing results, auto-compare with previous run** if one exists:

```bash
uv run "$RUNNER_SCRIPT" diff --eval-dir .eval --json
```

Parse the JSON and present a summary of what changed:
- How many answers changed
- Which specific questions changed (brief summary)
- Latency trends (faster/slower)
- Any new errors or resolved errors

Offer: "Want me to show the full diff for any of these, or dig into why something changed?"

**`report` argument:** Generate HTML report.

```bash
uv run "$RUNNER_SCRIPT" report --eval-dir .eval --template "$TEMPLATE_PATH" --open
```

Where TEMPLATE_PATH is the report_template.html next to runner.py.

**`diff` argument:** Show comparison.

```bash
uv run "$RUNNER_SCRIPT" diff --eval-dir .eval [run1] [run2]
```

Present the diff output. For changed answers, show the actual text differences clearly.

**`list` argument:** Show all runs.

```bash
uv run "$RUNNER_SCRIPT" list --eval-dir .eval
```

**Quoted question (ad-hoc):** Run a single question without saving a formal run.
- Read eval.yaml to determine the target
- Use the appropriate execution method to run just that question
- Show the answer inline
- Ask if the user wants to add this question to eval.yaml

### Step 4: Follow-up conversation

After presenting results, be ready for natural follow-up questions:

- **"Why did Q3 change?"** → Read the git diff between the two runs' git hashes. Read relevant source files. Explain what code change caused the answer change.
- **"Why is Q5 slow?"** → Look at the code path for that question. Check if there's a retrieval step, extra API call, or heavy processing.
- **"Show me the full diff"** → Show complete before/after text for each changed answer.
- **"Add more questions"** → Edit eval.yaml to add questions.
- **"Run only the support bot"** → Use `--target` flag.
- **"Run with version label"** → Use `--version` flag.

## Important

- The runner script does ALL mechanical work (running questions, saving results). You NEVER call the bot directly — always use the runner script.
- The runner outputs JSON to stdout. Parse it for structured data. Human-readable output goes to stderr.
- Results are stored in `.eval/runs/` as JSON files. You can read these directly for analysis.
- When comparing runs, always check if `.eval/runs/index.json` has enough runs before attempting a diff.
- If the runner script fails, read the error output and help the user fix the issue (wrong module path, endpoint not running, missing dependency, etc.)
- When creating eval.yaml, verify the target exists (check the file/function/endpoint before writing the config).
- The `.eval/` directory is git-ignored by default. Mention this to the user on first run.
