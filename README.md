# Hydra for agent CLIs

Hydra helps an agent review or change a project with several independent perspectives. It asks focused planning heads to inspect the same request, compares their evidence and tradeoffs, carries out the authorized work, then verifies the result. It works with Codex, Claude Code, Gemini CLI, and OpenCode.

You can install Hydra for every project you open, or add it to just one project. The setup script copies instructions and agent definitions; install and sign in to your chosen CLI separately.

## Quick start from GitHub

You need Git, Bash, and at least one of the supported agent CLIs. On Linux, macOS, or Windows with a Bash environment:

```bash
git clone https://github.com/Phatcharaphon-Hemnon/Hydra-Subagent-Skill.git
cd Hydra-Subagent-Skill
bash scripts/setup.sh
```

The menu lets you choose one CLI, several CLIs (for example `1,4`), or all four. It shows which CLI commands are currently detected, but you can select a CLI before installing it. The default destination is your user configuration, so Hydra is available in every project you open with that CLI.

For scripts or terminals without a menu, choose explicitly:

```bash
bash scripts/setup.sh --cli codex,claude
bash scripts/setup.sh --all
```

To install into only one project, give its existing directory:

```bash
bash scripts/setup.sh --cli codex,gemini --project /path/to/your-project
```

The shared skill is installed once in `.agents/skills/hydra-review/`. Only adapters for the CLIs you select are copied. OpenCode uses `XDG_CONFIG_HOME/opencode` for a global install when `XDG_CONFIG_HOME` is set, and `~/.config/opencode` otherwise. `scripts/install-global.sh` remains available for older instructions; it installs all four globally.

## Start Hydra in your project

Open a new CLI session in the project you want Hydra to work on, then use the matching entry point:

| CLI | Example |
| --- | --- |
| Codex | `$hydra-review Review the login flow for correctness and security.` |
| Claude Code | `/hydra Review the login flow for correctness and security.` |
| Gemini CLI | `/hydra Review the login flow for correctness and security.` |
| OpenCode | Select `hydra-orchestrator` and enter the request, or run `opencode run --agent hydra-orchestrator "Review the login flow"`. |

A change request works too: “Use Hydra to add password reset, then verify the result.” Hydra follows the instructions and permissions of the CLI and project where it runs. It does not automatically deploy or publish work.

## How Hydra works in your project

1. **Plan:** The primary agent inspects the project and selects 3–5 relevant heads: architecture, correctness, security, performance, and maintainability. Each selected head gets the same request and reports evidence, assumptions, tradeoffs, steps, and risks. They work independently and in parallel when the CLI allows it.
2. **Converge:** The primary agent compares the reports, resolves disagreements against the project evidence and your request, and chooses one actionable plan. Suggestions outside your request stay separate.
3. **Execute:** The primary agent performs the authorized changes. The planning heads do not edit files.
4. **Verify:** A separate verification head checks the result against the request and runs relevant tests and static checks. If it finds a failure, the primary agent repairs it and checks again.

For example, if you ask Hydra to fix a slow login page, the performance head may identify an expensive query, correctness may identify a behavior that must be preserved, and security may check that the fix does not expose account data. The primary agent chooses a fix that accounts for those findings, then the verification head checks the finished behavior.

If subagents are disabled or a delegation fails, Hydra performs the same lenses sequentially in the primary agent and tells you that the independence of the review was reduced. It reports which checks actually ran and which were inapplicable.

## Update or resolve a conflict

From your Hydra clone, pull updates and rerun the setup command with the same CLI selection:

```bash
git pull
bash scripts/setup.sh --cli codex,claude
```

Identical installed files are skipped. If a destination differs, setup stops before changing any files and lists the conflicts. Review them first. To replace them, add `--replace`; it backs up each changed file beside the original with a `.hydra-backup-...` suffix before installing the new copy.

```bash
bash scripts/setup.sh --cli codex,claude --replace
```

If a command is missing after setup, start a new CLI session. In Gemini CLI, `/commands reload`, `/agents reload`, and `/skills reload` can refresh a running session. For OpenCode, verify the `hydra-orchestrator` agent and `hydra-review` skill are visible. For Codex, check that `$hydra-review` appears among available skills.

## Other agent CLIs

For a CLI without a compatible skill or command system, paste this request into the project:

> Read `~/.agents/skills/hydra-review/SKILL.md` (or the project copy at `.agents/skills/hydra-review/SKILL.md`) and run Hydra for my request. Use independent specialists if available; otherwise use the sequential fallback and identify it. Follow all four stages and report actual verification results.

This repository is licensed under the [MIT License](LICENSE).
