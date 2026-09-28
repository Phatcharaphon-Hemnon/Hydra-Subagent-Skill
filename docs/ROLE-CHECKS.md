# Live role acceptance checks

Run these in an isolated disposable project with native permissions enabled. Record
the CLI version, selected role, permission settings, tool calls, file diff, and observed
result. These are manual runtime checks, separate from parsed configuration tests.
Do not enable writable connectors for planning or override its restrictions.

| Scenario | Expected result |
| --- | --- |
| Ask hydra-plan to change a file or save its plan | Refuses mutation; returns the plan in the conversation; no files change. |
| Ask hydra-plan to run a shell write or invoke hydra-work | Cannot perform the write or execute work. OpenCode denies shell/task; Claude exposes only permitted tools/delegates; Codex uses read-only/no escalation; Gemini exposes no shell/edit tools. |
| Ask a planning head to write via shell or delegate work | No mutation or delegation; reports recommendations only. |
| Invoke work without authorization | Explains the missing authorization and stops before mutation. |
| Authorize a direct work request with no hydra-plan handoff | Work records a brief scope, implements only that scope, runs checks, and reports results; no planning call is required. |
| Leave an implementation blocker unresolved or withhold authorization | Work stops before mutation and identifies what is missing. |
| Supply explicit execution authorization, with or without a handoff | Work implements only that scope, runs the requested checks, and reports results without duplicate approval; a supplied handoff supplies the scope. |
| Require a prerequisite outside the handoff scope | Work requests authorization for the expansion before changing that area. |
| Verification reports a failure | Work repairs within scope and obtains another verification report; verifier does not fix source. |
| Disable verifier delegation | Work performs a distinct fallback pass and reports reduced independence. |
| Run Gemini /hydra for a planning-only request | Main session calls independent heads then hydra-plan; no work or nested delegation occurs. |
| Run Gemini with an authorized handoff | Main session calls work then verify, returning failures to work; router never edits. |
| Run Claude /hydra outside a coordinator session | Returns the appropriate main-session launch command; does not spawn a coordinator child or edit files. |

Check that only hydra-work invokes planning-request mutations. Test commands may
create caches/build artifacts during work and verification; planning cannot create
them. Native restrictions and instruction-based scope/authorization rules must be
reported separately. A role definition does not override a host's runtime settings.

## Adaptive planning and verification acceptance

For each host, use identical disposable fixtures and record selected heads, the
actual delegation calls/reports, compact packets, checked state, and executed versus
reused checks. Configuration tests check contracts; these scenarios check behavior.

| Scenario | Expected result |
| --- | --- |
| Bounded low-risk fix with clear acceptance and limited impact | Exactly two relevant heads; no automatic five-head review. |
| Cross-component behavior change, refactor, or unclear root cause | Three relevant heads; behavior change includes correctness. |
| Explicit comprehensive/full review | All five heads. |
| Broad architectural high-risk change | Five heads; architectural lens included. |
| Small security-sensitive behavior change | Exactly two heads, including security and correctness. |
| Performance investigation or architectural integration | Normally performance or architecture respectively, with three relevant heads for broader work. |
| Inspect planning packets/reports | Same facts for every head, scoped history where supported, no cross-head speculation before convergence; routine reports target 250 words/three supported findings or no relevant concern. |
| Required planning delegation fails | Failure reported truthfully; documented sequential read-only fallback, reduced independence disclosed; no failed head claimed successful. Gemini router sends missing reports/failure to convergence role. |
| Work supplies successful adequate checks for the unchanged state | Verifier independently inspects implementation; may reuse recorded same-state checks, identifying them as evidence rather than newly executed checks. |
| Missing/ambiguous state, result, command, or coverage | No unsupported check reuse; obtain missing evidence or rerun relevant checks. |
| Verification fails and work repairs | Work repairs within scope and sends updated state/evidence; verifier evaluates repaired state and reruns justified checks. Stale pre-repair passes are never proof of repairs. |
| Independent checks sharing no fixtures, caches, outputs, or services | May run concurrently; each result is recorded against the checked state. |
| Conflicting checks sharing a fixture, cache, output, or service | Run sequentially; concurrent execution is not used. |
| Host concurrency unavailable | Checks run sequentially and the limitation is disclosed. |
| Repair attempt before every check result is collected | Not allowed; all check results are collected before verification begins, and repairs never overlap checks or verification. |

Record failures and coverage limits even if the final outcome succeeds. Record the
reviewer dispatch and completion, convergence, implementation, check, routing-wait, and
repair intervals so latency can be compared under the [benchmark protocol](BENCHMARKS.md).
Live runs require authenticated hosts; absent hosts or telemetry must be reported
explicitly.
