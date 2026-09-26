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

Pass the complete handoff and the user's authorization to `hydra-work`. It performs the authorized changes; the planning role never executes them. Respect the current CLI's plan mode, permissions, and approval requirements. Do not treat a head's suggestion as new user authorization. Keep track of actual changes and implementation adjustments within scope.

## 4. Verify

After execution, ask a separate verification head to inspect the result when available. Otherwise, perform a distinct verification pass and identify it as such. Trace the requested behavior and each implemented step to evidence. For code changes, run relevant changed-area tests, the project's existing full test suite when feasible, and configured lint or type checks. For documentation-only changes, inspect the final text; tests may be inapplicable. Exercise meaningful edge and failure cases where relevant. If no tests exist, add focused tests for changed behavior when useful. Fix failures, then rerun the affected checks; report any remaining limit plainly.

Finish with the converged decision, what changed, actual check results, and any material unresolved issue. Keep the report proportional to the task.

## Role and handoff contract

`hydra-plan` owns stages 1-2 only. Inspect using read-only tools, delegate only to the
five planning heads, and converge their independent reports. Never edit any files,
write a plan file, execute changes, invoke work or verification, or use side-effect
tools. Planning heads also stay read-only and must not delegate further. If delegation
is unavailable, perform the lenses sequentially within the same restrictions and
disclose reduced independence.

Return a handoff in the conversation with exactly these five headings:

- **task**: the requested outcome.
- **ordered steps**: actionable implementation steps.
- **files**: files or bounded components to change.
- **checks**: verification commands or inspection criteria.
- **authorized scope**: proposed change boundaries, exclusions, and any unresolved blockers.

Stop after the handoff. A handoff records proposed scope; the user's instructions
authorize execution. The entrypoint may route it to work when execution is already
authorized by the conversation. Never ask for duplicate approval.

`hydra-work` owns execution and checks. Before any mutation, require all five handoff
fields, no unresolved implementation blockers, and user authorization covering the
scope. If the handoff is missing, incomplete, or unauthorized, explain what is missing
and stop before mutation. Never create a new plan, spawn planning heads, or re-converge.
Implementation decisions and repairs within authorized scope are allowed; report them.
If completion requires expanding scope, stop the affected work and request authorization.

Delegate only to `hydra-verify` after implementation. Return failures to work for repair
within scope, then verify again. Verification never fixes source or weakens tests;
checks may write temporary caches or build artifacts. If verification delegation is
unavailable, work performs a distinct verification pass and discloses reduced independence.

## Platform routing and enforcement

- **OpenCode:** select the primary `hydra-plan` and `hydra-work` agents. Native permissions
  deny planner/head shell and edits, allow only named planning delegates, and restrict
  work delegation to verification. Unknown planning tools are denied by default.
- **Codex:** the main session delegates to the installed TOML roles. Planning uses a
  read-only sandbox without approval escalation; work uses workspace-write. Delegate
  allowlists are instructions, not native per-role permission rules. Live parent
  permission overrides and writable MCP tools can weaken isolation; do not enable
  writable connectors for planning or bypass its sandbox.
- **Claude Code:** launch `claude --agent hydra-plan` or `claude --agent hydra-work`.
  Main-session tool allowlists restrict reading/editing and named Agent delegates.
  Do not invoke these coordinators as child agents: named delegate restrictions are
  intended for the main thread. Planning heads expose only reading/search tools.
- **Gemini CLI:** the main session calls 3-5 planning heads independently, passes their
  reports to `hydra-plan` for convergence, and returns the handoff. After authorization,
  it invokes `hydra-work`, then `hydra-verify`, routing failures back to work for repair.
  Gemini child agents cannot delegate; neither role attempts nested calls. Roles use
  explicit native tool allowlists without inherited MCP or wildcard tools. The main
  session only routes reports and authorization; it does not perform edits itself.

For `/hydra` and `$hydra-review`, start with planning unless the user supplies an existing
complete handoff for execution. Route authorized execution to work and return actual
verification results. Do not silently execute a planning-only request.
