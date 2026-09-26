# Hydra overhead benchmark protocol

Adaptive planning is intended to reduce unnecessary overhead. No time or token
savings have been measured here; this document defines evaluation, not results.

## Conditions and fixtures

Compare single-agent work, original Hydra, and optimized adaptive Hydra. Pin the
original Hydra instruction baseline to `bf8f80aa5d282f787d5077f6aa12000b9f82fd30` and
record the optimized instruction revision/content identity. These identify workflow
instructions, not the target project's code: every condition starts from the same
fixture revision and identical relevant untracked files.

Use three fixed task classes: a small bounded fix, a cross-component change, and a
security-sensitive change. Freeze each prompt, acceptance criteria, starting code,
check commands, models, permissions, host configuration and CLI version before
running. Keep host/network/cache conditions as comparable as practical; record
unavoidable differences. Do not change models between conditions. The single-agent
condition completes equivalent work and final verification itself; original and
adaptive Hydra follow their respective instructions. Final acceptance is evaluated
by the same independent evaluator for all conditions.

Run three repetitions per condition and task class: 27 runs per tested host.
Evaluate Codex, Claude Code, Gemini CLI, and OpenCode separately where authenticated
hosts are available. Reset fixtures between runs and rotate condition order within
each repetition to reduce order effects. Do not run concurrent conditions sharing
resources. Retain transcripts and check evidence with sensitive data redacted.

## Per-run record

| Field | Record |
| --- | --- |
| Identity | Run ID, task class, condition, repetition, host/CLI and version, model/configuration, workflow identity, target starting revision/content identity |
| Timing | Elapsed wall-clock time from request through final verification, planning time through handoff, verification time summed across passes |
| Tokens | Total input and total output tokens across every agent/model call, including retries, fallback, work, verification and repairs |
| Context duplication | Duplicated input/context tokens when available, or per-call input sizes plus packet/history identities and repeated content spans sufficient to estimate duplication; label estimates |
| Calls | Model/agent call count, repair-loop count, selected planning heads and actual completed delegations |
| Evidence | Exact checks, checked state, exit codes, results, reused checks, omitted checks and coverage/environmental limits |
| Outcome | Acceptance result, failed assertions, investigation and repair details |

Use monotonic timestamps. Planning time is zero/not applicable for a condition
without a planning phase, identified explicitly. Include final independent
acceptance time consistently in elapsed and verification totals. Sum token usage
across agents rather than reporting only the main session. Mark unavailable token
or duplication telemetry **unknown**, never zero. Record cached input separately
when available; do not silently substitute billed tokens for total context tokens.

## Analysis and publication

Report medians separately by task class, condition, and host for timing, tokens,
calls and repair loops. Publish individual outcomes and ranges beside medians;
three repetitions are an initial benchmark, not a strong statistical conclusion.
Do not combine task classes into one overall savings number. Compare only matched
conditions and indicate unknown metrics and environmental differences.

Investigate every acceptance failure before claiming the optimized policy is
successful. Report failures and any changed fixtures/protocol; rerun matched
conditions after protocol changes. Claim faster or cheaper behavior only for the
specific measured task/host/metric where evidence supports it. Keep costs distinct
from token counts and use observed billing only if reporting costs.

Benchmark status: protocol only. Authenticated model runs and token telemetry are
required to populate results; configuration tests alone do not establish savings.
