#!/usr/bin/env bash
set -euo pipefail

hydra_script_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hydra_repo_dir="$(cd -- "$hydra_script_dir/.." && pwd)"
hydra_home="${HYDRA_INSTALL_HOME:-${HOME:?HOME is required}}"
hydra_xdg_config="${HYDRA_INSTALL_XDG_CONFIG_HOME:-${XDG_CONFIG_HOME:-$hydra_home/.config}}"
hydra_scope="global"
hydra_project=""
hydra_cli_arg=""
hydra_all=false
hydra_replace=false
hydra_temp=""
hydra_selected=()
hydra_sources=()
hydra_targets=()

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  hydra_bold=$'\033[1m'
  hydra_blue=$'\033[34m'
  hydra_green=$'\033[32m'
  hydra_reset=$'\033[0m'
else
  hydra_bold=""
  hydra_blue=""
  hydra_green=""
  hydra_reset=""
fi

usage() {
  cat <<'USAGE'
Usage: bash scripts/setup.sh [--cli codex,claude,gemini,opencode | --all]
                             [--project DIR] [--replace]

Without options in a terminal, choose one or more CLIs from a menu.
Global installation is the default. --project DIR installs only into that project.
--cli selects comma-separated CLI names; --all selects all four.
--replace backs up differing installed files before updating them.
Non-interactive use requires --cli or --all.
USAGE
}

cleanup_temp() {
  if [[ -n "$hydra_temp" && -e "$hydra_temp" ]]; then
    rm -f "$hydra_temp"
  fi
}
trap cleanup_temp EXIT

while (($# > 0)); do
  case "$1" in
    --cli)
      if (($# < 2)) || [[ -n "$hydra_cli_arg" ]]; then
        printf 'Expected one value after --cli.\n' >&2
        exit 2
      fi
      hydra_cli_arg="$2"
      shift 2
      ;;
    --all) hydra_all=true; shift ;;
    --project)
      if (($# < 2)) || [[ -n "$hydra_project" ]]; then
        printf 'Expected one directory after --project.\n' >&2
        exit 2
      fi
      hydra_scope="project"
      hydra_project="$2"
      shift 2
      ;;
    --replace) hydra_replace=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$hydra_all" == true && -n "$hydra_cli_arg" ]]; then
  printf 'Choose either --all or --cli, not both.\n' >&2
  exit 2
fi
if [[ "$hydra_scope" == project ]]; then
  if [[ ! -d "$hydra_project" ]]; then
    printf 'Project directory does not exist: %s\n' "$hydra_project" >&2
    exit 2
  fi
  hydra_project="$(cd -- "$hydra_project" && pwd)"
fi

add_cli() {
  local hydra_existing
  for hydra_existing in "${hydra_selected[@]}"; do
    [[ "$hydra_existing" == "$1" ]] && return 0
  done
  hydra_selected+=("$1")
}

parse_clis() {
  local hydra_input="$1" hydra_token
  local hydra_tokens=()
  IFS=',' read -r -a hydra_tokens <<< "$hydra_input"
  for hydra_token in "${hydra_tokens[@]}"; do
    hydra_token="${hydra_token#"${hydra_token%%[![:space:]]*}"}"
    hydra_token="${hydra_token%"${hydra_token##*[![:space:]]}"}"
    case "$hydra_token" in
      1|codex|Codex) add_cli codex ;;
      2|claude|Claude) add_cli claude ;;
      3|gemini|Gemini) add_cli gemini ;;
      4|opencode|OpenCode) add_cli opencode ;;
      a|A|all|All|ALL)
        add_cli codex
        add_cli claude
        add_cli gemini
        add_cli opencode
        ;;
      *) printf 'Unknown CLI choice: %s\n' "$hydra_token" >&2; return 1 ;;
    esac
  done
  ((${#hydra_selected[@]} > 0))
}

if [[ "$hydra_all" == true ]]; then
  parse_clis all
elif [[ -n "$hydra_cli_arg" ]]; then
  parse_clis "$hydra_cli_arg" || exit 2
elif [[ -t 0 && -t 1 ]]; then
  printf '%s╭──────────────────────────────────────╮%s\n' "$hydra_blue" "$hydra_reset"
  printf '%s│  Hydra setup · choose your agent CLIs  │%s\n' "$hydra_blue" "$hydra_reset"
  printf '%s╰──────────────────────────────────────╯%s\n' "$hydra_blue" "$hydra_reset"
  printf '  1  Codex        %s\n' "$(command -v codex >/dev/null 2>&1 && printf 'detected' || printf 'not detected')"
  printf '  2  Claude Code  %s\n' "$(command -v claude >/dev/null 2>&1 && printf 'detected' || printf 'not detected')"
  printf '  3  Gemini CLI   %s\n' "$(command -v gemini >/dev/null 2>&1 && printf 'detected' || printf 'not detected')"
  printf '  4  OpenCode     %s\n' "$(command -v opencode >/dev/null 2>&1 && printf 'detected' || printf 'not detected')"
  printf '  a  All four     q  Quit\n\n'
  while :; do
    printf '%sSelect numbers separated by commas (example: 1,4): %s' "$hydra_bold" "$hydra_reset"
    if ! IFS= read -r hydra_choice; then
      printf '\nSelection cancelled.\n'
      exit 0
    fi
    case "$hydra_choice" in q|Q|quit|Quit) printf 'Selection cancelled.\n'; exit 0 ;; esac
    hydra_selected=()
    if parse_clis "$hydra_choice"; then break; fi
    printf 'Choose 1–4, a, or q.\n'
  done
else
  printf 'Non-interactive setup requires --cli or --all.\n' >&2
  usage >&2
  exit 2
fi

add_file() {
  hydra_sources+=("$1")
  hydra_targets+=("$2")
}

if [[ "$hydra_scope" == global ]]; then
  hydra_agent_root="$hydra_home/.agents"
  hydra_codex_root="$hydra_home/.codex"
  hydra_claude_root="$hydra_home/.claude"
  hydra_gemini_root="$hydra_home/.gemini"
  hydra_opencode_root="$hydra_xdg_config/opencode"
  hydra_destination="Global user configuration"
else
  hydra_agent_root="$hydra_project/.agents"
  hydra_codex_root="$hydra_project/.codex"
  hydra_claude_root="$hydra_project/.claude"
  hydra_gemini_root="$hydra_project/.gemini"
  hydra_opencode_root="$hydra_project/.opencode"
  hydra_destination="$hydra_project"
fi

add_file "$hydra_repo_dir/.agents/skills/hydra-review/SKILL.md" "$hydra_agent_root/skills/hydra-review/SKILL.md"
for hydra_cli in "${hydra_selected[@]}"; do
  case "$hydra_cli" in
    codex)
      for hydra_source in "$hydra_repo_dir"/.codex/agents/hydra-*.toml; do
        add_file "$hydra_source" "$hydra_codex_root/agents/${hydra_source##*/}"
      done
      ;;
    claude)
      for hydra_source in "$hydra_repo_dir"/.claude/agents/hydra-*.md; do
        add_file "$hydra_source" "$hydra_claude_root/agents/${hydra_source##*/}"
      done
      add_file "$hydra_repo_dir/.claude/commands/hydra.md" "$hydra_claude_root/commands/hydra.md"
      ;;
    gemini)
      for hydra_source in "$hydra_repo_dir"/.gemini/agents/hydra-*.md; do
        add_file "$hydra_source" "$hydra_gemini_root/agents/${hydra_source##*/}"
      done
      add_file "$hydra_repo_dir/.gemini/commands/hydra.toml" "$hydra_gemini_root/commands/hydra.toml"
      ;;
    opencode)
      for hydra_source in "$hydra_repo_dir"/.opencode/agent/hydra-*.md; do
        add_file "$hydra_source" "$hydra_opencode_root/agent/${hydra_source##*/}"
      done
      ;;
  esac
done

hydra_conflicts=()
for hydra_index in "${!hydra_sources[@]}"; do
  hydra_source="${hydra_sources[$hydra_index]}"
  hydra_target="${hydra_targets[$hydra_index]}"
  if [[ ! -f "$hydra_source" ]]; then
    printf 'Missing source: %s\n' "$hydra_source" >&2
    exit 1
  fi
  if [[ -e "$hydra_target" || -L "$hydra_target" ]]; then
    if [[ -d "$hydra_target" ]]; then
      printf 'Target is a directory, not a file: %s\n' "$hydra_target" >&2
      exit 1
    fi
    if [[ -L "$hydra_target" || ! -f "$hydra_target" ]] || ! cmp -s "$hydra_source" "$hydra_target"; then
      hydra_conflicts+=("$hydra_target")
    fi
  fi
done

if ((${#hydra_conflicts[@]} > 0)) && [[ "$hydra_replace" == false ]]; then
  printf 'Setup stopped. Existing files differ:\n' >&2
  printf '  %s\n' "${hydra_conflicts[@]}" >&2
  printf 'Review them, then rerun with --replace to back them up and update.\n' >&2
  exit 1
fi

printf '\n%sHydra setup%s\n' "$hydra_bold" "$hydra_reset"
printf '  CLIs:        %s\n' "${hydra_selected[*]}"
printf '  Destination: %s\n' "$hydra_destination"
printf '  Files:       %d\n\n' "${#hydra_sources[@]}"

hydra_installed=0
hydra_skipped=0
hydra_backed_up=0
hydra_stamp="$(date +%Y%m%d%H%M%S).$$"
for hydra_index in "${!hydra_sources[@]}"; do
  hydra_source="${hydra_sources[$hydra_index]}"
  hydra_target="${hydra_targets[$hydra_index]}"
  if [[ ! -L "$hydra_target" && -f "$hydra_target" ]] && cmp -s "$hydra_source" "$hydra_target"; then
    ((hydra_skipped += 1))
    continue
  fi
  if [[ "$hydra_replace" == false && ( -e "$hydra_target" || -L "$hydra_target" ) ]]; then
    printf 'Target changed during installation: %s\n' "$hydra_target" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$hydra_target")"
  hydra_temp="$(mktemp "$hydra_target.hydra-tmp.XXXXXXXX")"
  cp -p "$hydra_source" "$hydra_temp"
  if [[ -e "$hydra_target" || -L "$hydra_target" ]]; then
    hydra_backup="$hydra_target.hydra-backup-$hydra_stamp"
    if [[ -e "$hydra_backup" || -L "$hydra_backup" ]]; then
      printf 'Backup already exists: %s\n' "$hydra_backup" >&2
      exit 1
    fi
    cp -Pp "$hydra_target" "$hydra_backup"
    printf 'Backed up %s\n' "$hydra_backup"
    ((hydra_backed_up += 1))
  fi
  mv -f "$hydra_temp" "$hydra_target"
  hydra_temp=""
  ((hydra_installed += 1))
done

printf '%sDone.%s %d installed, %d unchanged, %d backed up.\n' "$hydra_green" "$hydra_reset" "$hydra_installed" "$hydra_skipped" "$hydra_backed_up"
printf 'Start a new session in your selected agent CLI to use Hydra.\n'
