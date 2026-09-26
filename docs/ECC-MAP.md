# ECC Adapter Map (v2.2.x pinned)

ECC (`affaan-m/ECC`) is an external harness layer. Hydra stays a thin workflow overlay.
Do not vendor ECC skills into this repo. Install ECC via its own installer, one path per harness.

Pinned version: `ecc-universal@2.2.2` (verify with `npm view ecc-universal version` – registry showed `2.2.1` on 2026-09-26, use exact tag).
Scale: 68 agents, 292 skills, 94 commands. `hooks-runtime` only on `claude, claude-project, cursor, opencode, codebuddy`.

## Hydra (this repo) vs ECC destinations

| Hydra CLI | Hydra files (this repo) | ECC target | ECC command | Hooks? |
| --- | --- | --- | --- | --- |
| Claude Code | `.claude/agents/hydra-*.md`, `.claude/commands/hydra.md` | `claude` stable native `ecc@ecc` | `npx ecc-universal@2.2.2 setup` (scope `project`, default `--no-hooks` here) or `/plugin marketplace add https://github.com/affaan-m/ECC` + `/plugin install ecc@ecc` | profile-selection |
| Codex | `.codex/agents/hydra-*.toml` | `codex` supported native | `codex plugin marketplace add affaan-m/ECC && codex plugin add ecc@ecc` | native-trust, no Claude-style profiles |
| Gemini CLI | `.gemini/agents/hydra-*.md`, `.gemini/commands/hydra.toml` | `gemini` experimental minimal | `./install.sh --profile minimal --target gemini` | not-configured – instruction-only |
| OpenCode | `.opencode/agent/hydra-*.md` (singular `agent/`, 8 files: 5 heads + verify + plan + work), `.opencode/skills/hydra-review/` | `opencode` beta built plugin | in ECC checkout: `npm install && npm run build:opencode && ./install.sh --profile full --target opencode --enable-hooks` | adapter-opt-in |

No Hydra adapter exists for `qwen/kimi/cursor/zed/antigravity/hermes/openclaw/codebuddy/joycode` – ECC-only, defer to isolated test projects.

## Rules

1. One install path per harness. Never stack `plugin install` + `./install.sh --profile full` in the same harness – duplicates skills/hooks.
2. Project-scoped `minimal` first, one CLI at a time. Promote `minimal → core` only after `doctor` is green.
3. Explicit hooks decision: `--enable-hooks` vs `--no-hooks`. Default here is `--no-hooks` while Hydra heads stay read-only.
4. Snapshot before write: `git status --short`, backup `~/.claude ~/.codex ~/.gemini ~/.config/opencode`.
5. Verify after each CLI: `/plugin list` (Claude), `$hydra-review`, `opencode run --agent hydra-plan`, `node scripts/ecc.js doctor --target <cli>`.
6. Secrets: `.env`, `.env.*`, `*.key` are git-ignored. MCP keys via `process.env.*`, fail-closed, never logged.
7. Cleanup stacking: remove plugin, delete `~/.claude/rules/ecc/`, then `node scripts/ecc.js uninstall --target <cli> --dry-run`.

## Known gaps

- `scripts/setup.sh` supports only `codex,claude,gemini,opencode` – no `kimi/qwen` mapping.
- Installer tests derive file counts from the selected Hydra adapters. ECC remains external and is not included in those counts.
- OpenCode build must run inside ECC checkout, not this repo (Hydra `.opencode/package.json @opencode-ai/plugin 1.18.32` is unrelated).
- Windows: use `install.ps1 --profile minimal --target <name>`; Node 18+, Git, Claude Code 2.1+ required on PATH.
