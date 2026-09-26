---
name: hydra-review
description: "Use for a requested Hydra review or change: gather independent specialist plans, reconcile them, implement the authorized work, and verify the result. Also use when the user asks for multiple perspectives before execution."
metadata:
  workflow: plan-converge-execute-verify
---

# Hydra review and change workflow

Hydra gives several focused specialists the same task, compares their findings, completes the user's requested work, and checks the result. Use it when the user asks for Hydra or a multi-perspective review or implementation. It does not grant permission for actions beyond the user's request or the host CLI's rules.

## 1. Plan with independent heads

Inspect the project and the request first. Choose 3–5 relevant lenses from architecture, correctness, security, performance, and maintainability. Send each selected head the same task and project context. Ask them to work independently and in parallel when the CLI supports it; do not give one head another head's findings before they report.

Each head should stay within its lens and return:

- A short recommendation with concrete project evidence (file locations, behavior, commands, or observations).
- Assumptions and uncertainties that could change the recommendation.
- The main tradeoff or alternative considered, with a brief reason for its choice.
- An ordered, actionable plan and specific risks.

Ask for a concise, reviewable rationale, not private chain-of-thought. Do not demand findings from a lens when the project provides no evidence for them.

If subagents are unavailable, disabled, or a delegation call fails, perform the same lenses sequentially in the primary agent. Keep their notes separate until convergence and tell the user that this fallback reduced independence. Claim a head ran only when its delegation actually succeeded and returned a report.

## 2. Converge

Compare the reports against the user's goal and project evidence. Resolve conflicts explicitly, favoring the request and demonstrated behavior over head votes. Produce one plan with the chosen steps, the accepted tradeoffs, and checks that will show the request was met. Keep optional ideas outside the work scope. For broad or hard-to-reverse changes, show the plan before execution when the user has not already approved a concrete implementation.

## 3. Execute

Complete the authorized plan with the primary agent. Respect the current CLI's plan mode, permissions, and approval requirements. Do not treat a head's suggestion as new user authorization. Keep track of the actual changes and any deviations needed to make the result work.

## 4. Verify

After execution, ask a separate verification head to inspect the result when available. Otherwise, perform a distinct verification pass and identify it as such. Trace the requested behavior and each implemented step to evidence. For code changes, run relevant changed-area tests, the project's existing full test suite when feasible, and configured lint or type checks. For documentation-only changes, inspect the final text; tests may be inapplicable. Exercise meaningful edge and failure cases where relevant. If no tests exist, add focused tests for changed behavior when useful. Fix failures, then rerun the affected checks; report any remaining limit plainly.

Finish with the converged decision, what changed, actual check results, and any material unresolved issue. Keep the report proportional to the task.

## Plan / work split (where implemented)

Where a harness provides them, the pipeline may be split across two agents: `hydra-plan`
owns stages 1-2 (fan-out plus converge, read-only) and emits a handoff of task, ordered
steps, files, checks, and authorized scope; `hydra-work` owns stage 3 (executes only that
authorized scope) and then delegates stage 4 to the verification head. `hydra-plan` never
edits or executes; `hydra-work` never spawns planning heads or re-converges. The handoff,
not a head's suggestion, is the authorization boundary for execution.
