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

Codex discovers the standalone TOML roles in `.codex/agents/`; Gemini discovers
the shared `.agents/skills/` alias. Claude's `/hydra` command reads the shared
workflow directly, so it does not depend on Claude discovering that alias.
Use current CLI versions with custom-agent support; if a host disables delegation,
Hydra reports its sequential fallback instead of claiming independent heads ran.

## Start Hydra in your project

Open a new CLI session in the project you want Hydra to work on, then use the matching entry point:

| CLI | Example |
| --- | --- |
| Codex | `$hydra-review Plan a review of the login flow.` The main session routes planning to `hydra-plan` and authorized execution to `hydra-work`. |
| Claude Code | Launch `claude --agent hydra-plan`, then request the plan. For authorized execution, launch `claude --agent hydra-work` with the handoff and authorization. `/hydra` gives routing instructions when used outside a coordinator session. |
| Gemini CLI | `/hydra Plan a review of the login flow.` The main session gathers head reports, calls `hydra-plan`, and routes authorized work and verification separately. |
| OpenCode | Select `hydra-plan` to converge a plan, then `hydra-work` to execute it with verification, or run `opencode run --agent hydra-plan "Review the login flow"`. |

A change request works too: “Use Hydra to plan and implement password reset, then verify the result.” A planning-only request stops after the handoff. Work needs a complete handoff and user authorization; authorization already given in the conversation is retained without another approval question. For a separate work session, include the handoff and your execution instruction. Hydra follows the CLI's permissions and does not automatically deploy or publish work.

## How Hydra works in your project

1. **Plan:** `hydra-plan` inspects and gathers 3–5 independent heads: architecture, correctness, security, performance, and maintainability. In Gemini, the main session gathers reports because child agents cannot delegate. Neither planning roles nor heads write files or execute changes.
2. **Converge:** `hydra-plan` resolves disagreements against evidence and returns five handoff fields in the conversation: task, ordered steps, files, checks, authorized scope. It stops without writing a plan file.
3. **Execute:** `hydra-work` requires the complete handoff and user authorization before mutation. It implements, tests, and repairs within scope; expansion requires authorization. It never starts a new planning cycle.
4. **Verify:** `hydra-verify` independently checks the result. It reports failures to work for repair and re-verification. In Gemini, the main session routes these calls. Verification never fixes source or weakens tests; tests may write caches and build outputs.

For example, to fix a slow login page, planning heads may identify an expensive query, behavior to preserve, and account-data risks. The planner chooses a fix, work implements the authorized handoff, and verification checks the finished behavior.

If planning delegation fails, the planner performs the lenses sequentially using read-only tools and discloses reduced independence. If verification delegation fails, work performs a distinct verification pass and discloses the same limitation. It reports actual checks and results.

OpenCode uses native default-deny planning permissions, including shell denial and named delegates. Claude's main-session role tool lists restrict both tools and named delegates. Codex uses read-only planning sandboxes without escalation, but parent permission overrides can affect them and delegation restrictions are instructions. Gemini's role tool lists exclude editing/shell from planning; routing remains the main session's responsibility. Do not enable writable MCP tools or bypass planning restrictions. These adapters do not impose identical security boundaries on every host.

Configuration references: [Codex roles](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Claude agents](https://code.claude.com/docs/en/sub-agents), [Gemini agents](https://geminicli.com/docs/core/subagents/), [OpenCode permissions](https://opencode.ai/docs/permissions/).

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

If a command is missing after setup, start a new CLI session. In Gemini CLI, `/commands reload`, `/agents reload`, and `/skills reload` can refresh a running session. For OpenCode, verify the `hydra-plan`, `hydra-work`, and `hydra-verify` agents are visible. For Codex, check that `$hydra-review` appears among available skills.

Older OpenCode installations may still contain `hydra-orchestrator.md`. Setup does not delete retired files; inspect and remove that obsolete local definition manually so it cannot bypass the split.

## Check the adapters

With Python 3.11 or newer, install `requirements-dev.txt` in a virtual environment and run
`python3 -m unittest discover -s tests -v`. The suite parses native configuration
and checks installation behavior. [Role acceptance checks](docs/ROLE-CHECKS.md)
cover live CLI scenarios; configuration tests alone cannot prove model behavior.
With OpenCode installed, `HYDRA_NATIVE_ROLE_CHECK=1 python3 -m unittest discover -s tests -v`
also checks effective permissions after the host merges its configuration. This
loads agents without starting a model session and writes the CLI's usual log.
CI runs installation and native configuration parsing tests on
Linux and macOS with Python 3.11 and 3.14. It does not run authenticated model
sessions; follow the acceptance checklist for live role behavior.

## Using ECC alongside Hydra

ECC (`affaan-m/ECC`, pinned `ecc-universal@2.2.2`) is an external harness layer with
68 agents, 292 skills, and 94 commands. Hydra stays a thin overlay — do not copy ECC
files into this repo. See `docs/ECC-MAP.md` for the per-CLI adapter map.

- Claude Code (stable): `npx ecc-universal@2.2.2 setup` (scope `project`), or
  `/plugin marketplace add https://github.com/affaan-m/ECC` + `/plugin install ecc@ecc`.
- Codex (supported): `codex plugin marketplace add affaan-m/ECC && codex plugin add ecc@ecc`.
- OpenCode (beta): in an ECC checkout run `npm install && npm run build:opencode && ./install.sh --profile full --target opencode --enable-hooks`.
- Gemini (experimental minimal): `./install.sh --profile minimal --target gemini` — no hooks-runtime.

One path per harness, project-scoped `minimal` first, explicit `--enable-hooks` vs
`--no-hooks` (default `--no-hooks` here), then `node scripts/ecc.js doctor --target <cli>`.

## Other agent CLIs

For a CLI without a compatible skill or command system, paste this request into the project:

> Read `~/.agents/skills/hydra-review/SKILL.md` (or the project copy at `.agents/skills/hydra-review/SKILL.md`) and run Hydra for my request. Use independent specialists if available; otherwise use the sequential fallback and identify it. Follow all four stages and report actual verification results.

This repository is licensed under the [MIT License](LICENSE).
