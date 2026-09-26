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

Work requires the handoff plus authorization from the user, including authorization
already given in the conversation. Retain that authorization when transferring the
handoff so work does not ask for duplicate approval. Never execute a planning-only
request. Work runs checks and delegates only to hydra-verify, repairing failures
within scope before verifying again.
