#!/usr/bin/env bash
# CivicLens Gardener — Task Generator for GitHub Copilot Agent
#
# Generates the combined audit + fix task description for the GitHub Copilot
# coding agent. The agent receives this task and autonomously audits the repo,
# detects intent drift, fixes issues, and creates a PR if needed.
#
# Usage:
#   ./scripts/gardener-audit.sh --task    # Print task description for the agent
#
# Required environment (for --task mode):
#   GARDENER_LINT_RESULT    — Result of the frontend lint job
#   GARDENER_PYLINT_RESULT  — Result of the Python lint job
#   GARDENER_BUILD_RESULT   — Result of the Next.js build job
#   GARDENER_TEST_RESULT    — Result of the Python test job

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATE_STAMP="$(date -u +'%Y-%m-%d')"

cd "$REPO_ROOT"

if [ "${1:-}" != "--task" ]; then
  echo "Usage: $0 --task"
  echo "  --task    Print the audit task description for the GitHub Copilot agent"
  exit 1
fi

# ─── Collect upstream health check results ─────────────────────────
LINT_RESULT="${GARDENER_LINT_RESULT:-unknown}"
PYLINT_RESULT="${GARDENER_PYLINT_RESULT:-unknown}"
BUILD_RESULT="${GARDENER_BUILD_RESULT:-unknown}"
TEST_RESULT="${GARDENER_TEST_RESULT:-unknown}"

HAS_FAILURES="false"
FAILURE_SUMMARY=""
# Treat any non-success result (failure, cancelled, skipped, unknown) as a signal
# that the check needs investigation, not just explicit "failure".
if [ "$LINT_RESULT" != "success" ]; then
  HAS_FAILURES="true"
  FAILURE_SUMMARY="${FAILURE_SUMMARY}
- LINT ${LINT_RESULT^^}: Run 'npm run lint' and 'npx tsc --noEmit' to see errors. Fix lint and type errors in src/."
fi
if [ "$PYLINT_RESULT" != "success" ]; then
  HAS_FAILURES="true"
  FAILURE_SUMMARY="${FAILURE_SUMMARY}
- PYTHON LINT ${PYLINT_RESULT^^}: Run 'ruff check src/ tests/' to see errors. Fix ruff violations in Python code."
fi
if [ "$BUILD_RESULT" != "success" ]; then
  HAS_FAILURES="true"
  FAILURE_SUMMARY="${FAILURE_SUMMARY}
- BUILD ${BUILD_RESULT^^}: Run 'npm run build' to see errors. Fix build-breaking issues in src/."
fi
if [ "$TEST_RESULT" != "success" ]; then
  HAS_FAILURES="true"
  FAILURE_SUMMARY="${FAILURE_SUMMARY}
- TESTS ${TEST_RESULT^^}: Run 'pytest tests/ -v --tb=short' to see failures. Fix failing tests by fixing the code (not the test expectations)."
fi

# ─── Output the combined audit + fix task ──────────────────────────
cat << TASK_EOF
You are the CivicLens Gardener — an autonomous maintenance agent responsible for
keeping this repository aligned with its stated design intent.

## Upstream Health Check Results

| Check | Result |
|-------|--------|
| Frontend Lint & TypeCheck | ${LINT_RESULT} |
| Python Lint (Ruff) | ${PYLINT_RESULT} |
| Next.js Build | ${BUILD_RESULT} |
| Python Tests | ${TEST_RESULT} |
$(if [ "$HAS_FAILURES" = "true" ]; then
  echo ""
  echo "FAILURES DETECTED — These must be investigated and included in your report:"
  echo "${FAILURE_SUMMARY}"
  echo ""
fi)

## Phase 1 — Audit

### Context Recovery (Token Optimization)

FIRST, check if .gardener-context.md exists. If it does, read it — it contains
a condensed snapshot from your last audit run: which arrows were audited, what their
status was, which specs were implemented, and key findings. Use this to SKIP
re-analyzing unchanged areas and focus your effort on:
- Arrows whose code files have changed since the last audit (check git log)
- New specs or arrows that weren't in the previous context
- Previously flagged drift that may now be resolved

If .gardener-context.md does not exist, this is a fresh audit — analyze everything.

LAST, after completing your audit and writing the JSON report, also write/update
.gardener-context.md with a condensed snapshot for the next run. Format:

# Gardener Context — {date}
## Arrow Status Snapshot
(table of Arrow, Status, Drift, Last Audited)
## Implemented Specs (checked off)
(list of spec IDs that are implemented)
## Key Findings Carried Forward
(findings that weren't resolved)
## Files Hash (for change detection)
(output of: git log --oneline -1 -- docs/ src/ for quick staleness check)

### Your Mandate

1. Read the arrows of intent — Start with docs/arrows/index.yaml to understand
   the project's arrow structure, dependencies, and status. Then read each arrow
   detail file referenced in the index.

2. Read the EARS specifications — Read every file in docs/specs/ to understand
   the granular requirements for each arrow.

3. Audit code against specs — For each arrow:
   a. Check if the code files listed in the arrow's "Code" section actually exist.
   b. Search for @spec annotations in the codebase and cross-reference them against
      the EARS spec IDs. Find specs that have code but aren't annotated, and annotations
      that reference non-existent specs.
   c. For implemented specs, verify the code actually fulfills the requirement (read the
      code, compare to spec language).
   d. Check if arrow status fields (status, drift) are accurate given current code state.

4. Audit CI/CD pipeline coverage — Read .github/workflows/ingest.yml and verify:
   a. Every implemented ingestion source (clients + scrapers) has a corresponding
      CI/CD job or trigger. Flag sources that are built but not scheduled.
   b. The normalization pipeline (src/pipeline/normalize.py) has all implemented
      sources registered in its NORMALIZERS dict. Flag commented-out or missing entries.
   c. The embedding pipeline runs after normalization and covers all Silver tables.
   d. Schedules are appropriate (state bills every 6h, local scrapers daily).
   e. Data flows end-to-end: Bronze → Silver → Gold for each source. Flag any source
      that is ingested to Bronze but never normalized or embedded.

5. Detect drift — Identify gaps between intent and implementation:
   - Specs marked as active but with no corresponding code
   - Code that exists but doesn't match its spec
   - Arrow status that's stale (e.g., says MAPPED but code is partially implemented)
   - Missing test coverage for implemented specs
   - Files referenced in arrows that don't exist yet
   - @spec annotations in code that reference deferred or non-existent specs
   - Ingestion sources built but not scheduled in CI/CD
   - Pipeline stages incomplete (Bronze exists but Silver/Gold missing)
   - Normalizers implemented but not registered in NORMALIZERS dict

6. Produce a JSON report — Output a JSON object to .gardener-report.json with this structure:
   {
     "date": "YYYY-MM-DD",
     "summary": "One paragraph overall assessment",
     "arrows": [
       {
         "name": "arrow-name",
         "declared_status": "MAPPED",
         "actual_status": "PARTIALLY_IMPLEMENTED",
         "drift_detected": true,
         "findings": [
           {
             "type": "missing_code|stale_status|unlinked_spec|missing_test|broken_reference|security|pipeline_gap|unscheduled_source",
             "severity": "high|medium|low",
             "spec_id": "DASH-VIEW-001",
             "detail": "Description of the finding",
             "recommendation": "What should be done"
           }
         ]
       }
     ],
     "stats": {
       "total_specs": 0,
       "implemented_specs": 0,
       "partially_implemented": 0,
       "not_started": 0,
       "coverage_pct": 0
     }
   }

7. Security threat model — Analyze the codebase for security concerns:
   a. API route protection: Are all API routes properly authenticated/rate-limited?
      Check src/app/api/ for missing auth checks, open endpoints, or missing input validation.
   b. Database security: Are RLS policies in place? Check supabase/migrations/ for
      row-level security on all tables. Verify anon role has minimal permissions.
   c. Injection vectors: Check for unsanitized user input in SQL queries, shell commands,
      or HTML rendering. Look for template literal SQL, dangerouslySetInnerHTML, exec/spawn.
   d. Secret exposure: Verify no API keys, tokens, or credentials are hardcoded in source.
      Check that all secrets flow through environment variables.
   e. Dependency risk: Note any known-vulnerable or unmaintained dependencies.
   f. Data flow trust boundaries: Trace user input from chat -> API -> RAG -> LLM -> response.
      Identify where prompt injection, data exfiltration, or context manipulation could occur.
   g. CORS/CSP: Check Next.js config for security headers (Content-Security-Policy,
      X-Frame-Options, X-Content-Type-Options).

   Add a "security" section to the JSON report:
   {
     "security": {
       "threat_level": "low|medium|high|critical",
       "findings": [
         {
           "category": "auth|rls|injection|secrets|dependencies|headers|prompt_injection",
           "severity": "critical|high|medium|low",
           "location": "file:line",
           "detail": "Description",
           "recommendation": "Fix"
         }
       ]
     }
   }

8. Assess overall state goal achievement — Evaluate whether the project is on track
   to deliver its stated purpose: "Plain-language access to the laws that affect you."
   Consider: Is the data pipeline working? Is the chat functional? Is the dashboard
   useful? What's the biggest gap between current state and ideal state?

### Audit Rules

- Be thorough but honest. Don't inflate findings.
- Every finding must reference a specific spec ID or file path.
- Distinguish between "not yet started" (expected for MAPPED arrows) and "drift"
  (code exists but diverges from spec, or status is wrong).
- Do NOT modify any code during the audit phase. Only read and report.
- Write the JSON report to .gardener-report.json in the repo root.
- Write/update .gardener-context.md with the condensed context snapshot for next run.
- After writing the report, print a human-readable summary to stdout.

## Phase 2 — Fix

After completing the audit, proceed to fix issues found. Read .gardener-report.json.

Priority order (fix the most critical issues first):

### Priority 1: Fix Failing Health Checks

If ANY upstream health check failed, this is your TOP PRIORITY. Before doing
anything else:

a. REPRODUCE the failure — run the failing command yourself to see the exact errors:
   - Lint failed: run 'npx next lint' and 'npx tsc --noEmit'
   - Python lint failed: run 'ruff check src/ tests/'
   - Build failed: run 'npx next build' (may need env vars — check .env.example)
   - Tests failed: run 'pytest tests/ -v --tb=short'

b. READ the error output carefully. Understand the root cause.

c. FIX the code that is causing the failure. Common patterns:
   - Type errors: fix the TypeScript types, add missing type annotations
   - Lint errors: fix the lint violations in the source code
   - Ruff errors: fix Python style/import issues
   - Test failures: fix the APPLICATION CODE so tests pass (never weaken tests)
   - Build failures: fix import errors, missing dependencies, config issues

d. RE-RUN the command to verify your fix actually works before moving on.

### Priority 2: Fix Drift (Intent Alignment)

After all health checks are green (or were already passing):

1. Update arrow drift fields — For each arrow where drift was detected, update
   docs/arrows/index.yaml to set the drift field with a concise description
   and update sampled to today's date.

2. Fix stale status — If an arrow's actual status differs from declared status
   (e.g., code partially exists but status says MAPPED), update the status field.

3. Add missing @spec annotations — If code implements a spec but lacks the
   @spec annotation, add it. Use the format:
   - Python: # @spec SPEC-ID-001
   - TypeScript: // @spec SPEC-ID-001

4. Check off implemented specs — In docs/specs/*.md, change - [ ] to - [x]
   for specs that the code verifiably implements.

5. Update arrow detail docs — If the "Key Findings" section says "None yet",
   add findings based on what exists in the code.

6. Propose small code improvements — If a spec is almost implemented but has
   a minor gap (e.g., missing legal disclaimer, missing null check), fix it.
   Do NOT attempt large features or major refactors.

### Fix Rules

- ALWAYS fix failing health checks before addressing drift.
- Fix the code, not the tests — if a test fails, the code is wrong.
- Only make changes that are clearly correct and low-risk.
- Prefer documentation accuracy over code changes (for drift fixes).
- Never delete code or remove features.
- After fixing health checks, re-run the command to verify the fix.
- Limit total changes to what's reviewable in a single PR (<500 lines diff).
- After making all changes, create a PR to the dev branch with title:
  "Gardener: intent alignment fixes ${DATE_STAMP}"
  Label the PR with "gardener".

## Start

Begin Phase 1 by reading docs/arrows/index.yaml, then systematically audit each
arrow. After completing the audit and writing .gardener-report.json, proceed to
Phase 2 and fix any issues found.
TASK_EOF

