---
description: Run Hydra's multi-perspective plan, execution, and verification workflow
---

Run Hydra for this request: $ARGUMENTS

Read the `hydra-review` workflow at `.agents/skills/hydra-review/SKILL.md` in this project, or `~/.agents/skills/hydra-review/SKILL.md` for a global installation. If the request is missing, ask what work to review or change.

Use the role and handoff contract. Start with planning unless a complete existing
handoff is supplied for execution. Run coordinators as main sessions using
`claude --agent hydra-plan` and `claude --agent hydra-work`; never spawn them as
child agents or execute changes in this routing session. If already in the matching
coordinator session, follow its role. Otherwise return the matching launch command
and the task or handoff for the user to carry into that session; do not launch a CLI
inside a CLI. A planning session always stops after returning its handoff.

Work requires user authorization for the scope, including authorization already given
in the conversation; a hydra-plan handoff is optional and supplies scope when present.
Retain that authorization when transferring a handoff so work does not ask for duplicate
approval. Never execute a planning-only
request. Work runs checks and delegates only to hydra-verify, repairing failures
within scope before verifying again. Use scoped context instead of redundant planning
transcripts: work receives the complete handoff and authorization; verification receives
the handoff, implementation adjustments, and checked-state evidence. Dispatch independent
heads in parallel within host limits where supported and batch independent reads. Run
independent checks concurrently only when fixtures, caches, outputs, and services cannot
conflict, otherwise sequentially, and collect every check result before verification.
