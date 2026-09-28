---
name: hydra-review
description: "Use for a requested Hydra review or change: gather independent specialist plans, reconcile them, implement the authorized work, and verify the result. Also use when the user asks for multiple perspectives before execution."
metadata:
  workflow: plan-converge-execute-verify
---

# Hydra review and change workflow

Hydra gives several focused specialists the same task, compares their findings, completes the user's requested work, and checks the result. Use it when the user asks for Hydra or a multi-perspective review or implementation. It does not grant permission for actions beyond the user's request or the host CLI's rules.

## 1. Plan with independent heads

Inspect the project and request first. Classify scope and risk before selecting relevant lenses from architecture, correctness, security, performance, and maintainability. Use this adaptive policy; do not automatically select all five heads.

| Task class | Heads | Selection criteria |
| --- | --- | --- |
| Bounded low-risk | 2 | Limited affected area, clear acceptance criteria, no broad architectural impact, and no comprehensive review request. |
| Broader | 3 | Cross-component changes, unclear root causes, refactors, integration work, performance investigations, or behavior changes spanning multiple areas. |
| Comprehensive or high-risk architecture | 5 | Explicit comprehensive/full review, or a change that is broad, architectural, and high-risk enough to justify all lenses. |

Head count and required lenses are separate. Comprehensive/high-risk architecture takes precedence over broader work, which takes precedence over bounded work. Select remaining heads by relevance. Explain selection only when useful.

| Task property | Lens | Requirement |
| --- | --- | --- |
| Behavior-changing | correctness | Required |
| Security-sensitive | security | Required |
| Performance-focused | performance | Normally include |
| Architectural | architecture | Normally include |

Construct one compact factual packet containing goal, constraints, relevant paths/files/modules/symbols/commands, acceptance criteria, established facts, and important unknowns to investigate. Send every selected head the same packet; use scoped context rather than unnecessary full conversation inheritance when supported. Exclude unrelated history, duplicated explanations, and speculative conclusions from other heads. Heads work independently. Dispatch all selected heads together in parallel within host limits when the host supports it, and batch independent reads so shared discovery is performed once; keep their reports separate until convergence.

Routine reports target 250 words or fewer and at most three material, evidence-backed findings. Each finding needs paths, symbols, observed behavior, commands, configuration, or test evidence; include actionable recommendations and material uncertainties/tradeoffs within that budget. Exceed the limit only for a concrete blocker, security issue, missing evidence, or another issue necessary for a correct handoff. Allow “No relevant concern.” with brief evidence when needed. Request reviewable rationale, never private chain-of-thought.

If subagents are unavailable, disabled, or a delegation call fails, perform the same lenses sequentially in the primary agent. Keep their notes separate until convergence and tell the user that this fallback reduced independence. Claim a head ran only when its delegation actually succeeded and returned a report.

## 2. Converge

Compare the reports against the user's goal and project evidence. Resolve conflicts explicitly, favoring the request and demonstrated behavior over head votes. Produce one plan with the chosen steps, the accepted tradeoffs, and checks that will show the request was met. Keep optional ideas outside the work scope. For broad or hard-to-reverse changes, show the plan before execution when the user has not already approved a concrete implementation.

## 3. Execute

Pass the user's authorization to `hydra-work`, together with the handoff when planning produced one. Work can also run directly on an authorized request with no `hydra-plan` handoff; it then records a brief scope (task, files or bounded components, and checks) before editing. When a handoff is present it carries concise source references, established facts, acceptance criteria, and relevant uncertainties so work does not repeat discovery; work re-reads the cited current source before editing and stops if a carried fact no longer holds. Use scoped context rather than inheriting the whole planning conversation, and exclude redundant planning transcripts and the other heads' reports. It performs the authorized changes; the planning role never executes them. Respect the current CLI's plan mode, permissions, and approval requirements. Do not treat a head's suggestion as new user authorization. Keep track of actual changes and implementation adjustments within scope.

## 4. Verify

After execution, ask a separate verification head to independently inspect the resulting implementation when available. Otherwise, perform a distinct verification pass and disclose reduced independence. Work supplies a compact evidence packet: changed files/components; exact checked code/worktree/revision state; exact check commands; exit codes; concise results; failures; checks not executed; and known coverage gaps or environmental limitations. A revision SHA alone is insufficient for a dirty worktree: record the worktree diff/content fingerprint including relevant untracked files, or an equivalent state identity. Refresh the packet after repairs.

The evidence packet uses these reviewable Markdown fields (no runtime schema):

| Field | Contents |
| --- | --- |
| Changed components | Files/components changed |
| Checked state | Revision plus staged/unstaged and relevant untracked content identity, or equivalent complete snapshot |
| Executed checks | Exact command, exit code and concise result for each check, tied to checked state |
| Failures | Failed checks and observed errors |
| Not executed | Omitted checks and reasons |
| Limits | Known coverage gaps and environmental limitations |

Verification receives the handoff, work's implementation adjustments, and the checked-state evidence; use scoped context and exclude redundant planning transcripts. Collect every check result before verification begins. Run independent checks concurrently only when resources and mutable fixtures, caches, outputs, and services cannot conflict; otherwise run them sequentially.

Verification independently traces the request and implemented steps to evidence and checks meaningful edge and failure cases where relevant. Reuse an executed check only when it succeeded against the same code state, its command and result are known, and it adequately covers the verified behavior. Do not blindly rerun every expensive check. Rerun when code changed, the result failed or is stale/ambiguous, relevant coverage is missing, repair occurred, or independent execution evidence is needed. Verification must evaluate repaired code and never use stale pre-repair results as proof. Relevant changed-area tests, the existing full suite when feasible, and configured lint/type checks remain required coverage; satisfied same-state checks can supply that evidence. Documentation-only work may require inspection rather than tests. Report actual execution separately from reused evidence.

Finish with the converged decision, what changed, actual check results, and any material unresolved issue. Keep the report proportional to the task.

## Role and handoff contract

`hydra-plan` owns stages 1-2 only. Inspect using read-only tools, delegate only to the
five planning heads, and converge their independent reports. Never edit any files,
write a plan file, execute changes, invoke work or verification, or use side-effect
tools. Planning heads also stay read-only and must not delegate further. If delegation
is unavailable, perform the lenses sequentially within the same restrictions and
disclose reduced independence.

Return a handoff in the conversation with exactly these five headings:

- **task**: the requested outcome and its acceptance criteria.
- **ordered steps**: actionable implementation steps, each carrying concise source references (paths/symbols), established facts, and relevant uncertainties so work does not repeat discovery.
- **files**: files or bounded components to change.
- **checks**: verification commands or inspection criteria tied to the acceptance criteria.
- **authorized scope**: proposed change boundaries, exclusions, and any unresolved blockers.

Stop after the handoff. A handoff records proposed scope; the user's instructions
authorize execution. The entrypoint may route it to work when execution is already
authorized by the conversation. Never ask for duplicate approval.

`hydra-work` owns execution and checks. Before any mutation, require explicit user
authorization covering the scope and no unresolved implementation blockers; a
`hydra-plan` handoff is optional. If a complete handoff is present, honor its five
fields; if it is absent, record a brief scope (task, files or bounded components, and
checks) from the authorized request before editing. If the request is unauthorized or a
blocker is unresolved, explain what is missing and stop before mutation. Re-read the handoff's cited current source before editing and stop if a carried fact no longer holds. Collect every check result before verification: never overlap repairs with checks or verification. Run independent checks concurrently only when resources and mutable fixtures, caches, outputs, and services cannot conflict; otherwise run them sequentially. Never create a new plan, spawn planning heads, or re-converge.
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
- **Gemini CLI:** the main session selects and calls 2 / 3 / 5 planning heads independently using the adaptive policy, dispatches them in parallel within host limits when supported, batches independent reads, passes their reports to `hydra-plan` for convergence, and returns the handoff. After authorization,
  it invokes `hydra-work`, then `hydra-verify`, routing failures back to work for repair.
  Gemini child agents cannot delegate; neither role attempts nested calls. Roles use
  explicit native tool allowlists without inherited MCP or wildcard tools. The main
  session only routes reports and authorization; it does not perform edits itself.

For `/hydra` and `$hydra-review`, start with planning unless the user supplies an existing
complete handoff for execution. Route authorized execution to work and return actual
verification results. Do not silently execute a planning-only request.
