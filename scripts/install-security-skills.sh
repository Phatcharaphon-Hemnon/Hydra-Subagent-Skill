#!/usr/bin/env bash
# Optional installer for external cybersecurity skills.
# Clones a PINNED revision outside every auto-discovered skills directory and
# validates paths/symlinks. Never copies anything into .agents/skills/.
# Bundled skill scripts are never executed automatically.
set -euo pipefail

hydra_script_dir="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hydra_repo_dir="$(cd -- "$hydra_script_dir/.." && pwd)"
hydra_source_url="https://github.com/mukul975/Anthropic-Cybersecurity-Skills"
hydra_vendor_dir="$hydra_repo_dir/vendor/anthropic-cybersecurity-skills"
hydra_pin=""
hydra_replace=false
hydra_check_only=""

usage() {
  cat <<'USAGE'
Usage: bash scripts/install-security-skills.sh --pin <commit-sha|tag> [--replace]
       bash scripts/install-security-skills.sh --check-only <dir>

Options:
  --pin SHA-OR-TAG   Required. A full commit SHA pins immutably; a tag is
                     resolved to its commit SHA before checkout (floating refs
                     are never checked out).
  --replace          Back up an existing checkout and replace it with the pin.
  --check-only DIR   Offline validation only: check DIR for path traversal and
                     unsafe symlinks without cloning. Exit 0 when clean.
USAGE
}

while (($# > 0)); do
  case "$1" in
    --pin)
      if (($# < 2)) || [[ -n "$hydra_pin" ]]; then
        printf 'Expected one value after --pin.\n' >&2
        exit 2
      fi
      hydra_pin="$2"
      shift 2
      ;;
    --replace) hydra_replace=true; shift ;;
    --check-only)
      if (($# < 2)) || [[ -n "$hydra_check_only" ]]; then
        printf 'Expected one directory after --check-only.\n' >&2
        exit 2
      fi
      hydra_check_only="$2"
      shift 2
      ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

# Validate a directory tree: reject path traversal in tracked names and
# symlinks that are absolute or escape the root. Prints violations to stderr.
validate_tree() {
  local root="$1" failures=0
  root="$(realpath -m "$root")"
  if [[ ! -d "$root" ]]; then
    printf 'Not a directory: %s\n' "$1" >&2
    return 2
  fi
  if [[ -e "$root/.git" ]] || [[ -d "$root/.git" ]]; then
    : # git checkouts carry their own metadata; names below are still checked
  fi
  local entry
  while IFS= read -r -d '' entry; do
    local rel="${entry#$root/}"
    if [[ "$rel" == *".."* ]]; then
      printf 'Rejected path traversal: %s\n' "$entry" >&2
      failures=$((failures + 1))
    fi
  done < <(find "$root" -mindepth 1 -path "$root/.git" -prune -o -print0)
  local link target resolved
  while IFS= read -r -d '' link; do
    target="$(readlink "$link")"
    case "$target" in
      /*)
        printf 'Rejected absolute symlink: %s -> %s\n' "$link" "$target" >&2
        failures=$((failures + 1))
        continue
        ;;
    esac
    resolved="$(realpath -m "$(dirname "$link")/$target")"
    case "$resolved" in
      "$root"/*) ;;
      *)
        printf 'Rejected escaping symlink: %s -> %s\n' "$link" "$target" >&2
        failures=$((failures + 1))
        ;;
    esac
  done < <(find "$root" -path "$root/.git" -prune -o -type l -print0)
  if ((failures > 0)); then
    printf '%d unsafe path(s) found under %s\n' "$failures" "$root" >&2
    return 1
  fi
  return 0
}

if [[ -n "$hydra_check_only" ]]; then
  validate_tree "$hydra_check_only"
  printf 'Directory is clean: %s\n' "$hydra_check_only"
  exit 0
fi

if [[ -z "$hydra_pin" ]]; then
  printf 'A pin is required: rerun with --pin <commit-sha|tag>.\n' >&2
  usage >&2
  exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  printf 'git is required to install security skills.\n' >&2
  exit 1
fi

# Resolve the pin to an immutable commit SHA.
if [[ "$hydra_pin" =~ ^[0-9a-fA-F]{40}$ ]]; then
  hydra_sha="$hydra_pin"
else
  hydra_sha="$(git ls-remote "$hydra_source_url" "refs/tags/$hydra_pin" | awk '{print $1}' | head -n 1)"
  if [[ -z "$hydra_sha" ]]; then
    # Fall back to annotated-tag peel (^{}) before giving up.
    hydra_sha="$(git ls-remote "$hydra_source_url" | awk -v tag="refs/tags/$hydra_pin" '$2 == tag || $2 == tag "^{}" {print $1}' | tail -n 1)"
  fi
  if [[ -z "$hydra_sha" ]]; then
    printf 'Could not resolve tag to a commit SHA: %s\n' "$hydra_pin" >&2
    exit 1
  fi
  printf 'Resolved tag %s to %s\n' "$hydra_pin" "$hydra_sha"
fi

if [[ -e "$hydra_vendor_dir" || -L "$hydra_vendor_dir" ]]; then
  if [[ -f "$hydra_vendor_dir/.hydra-pin" ]] && grep -qx "$hydra_sha" "$hydra_vendor_dir/.hydra-pin" 2>/dev/null; then
    printf 'Security skills already at pin %s; nothing to do.\n' "$hydra_sha"
    exit 0
  fi
  if [[ "$hydra_replace" != true ]]; then
    printf 'Existing checkout differs from pin %s.\n' "$hydra_sha" >&2
    printf 'Review it, then rerun with --replace to back it up and update.\n' >&2
    exit 1
  fi
  hydra_backup="$hydra_vendor_dir.hydra-backup-$(date +%Y%m%d%H%M%S).$$"
  mv -- "$hydra_vendor_dir" "$hydra_backup"
  printf 'Backed up previous checkout to %s\n' "$hydra_backup"
fi

mkdir -p "$(dirname "$hydra_vendor_dir")"
git clone --no-checkout "$hydra_source_url" "$hydra_vendor_dir"
git -C "$hydra_vendor_dir" checkout --detach "$hydra_sha"

if ! validate_tree "$hydra_vendor_dir"; then
  printf 'Validation failed; removing unsafe checkout.\n' >&2
  rm -rf -- "$hydra_vendor_dir"
  exit 1
fi

printf '%s\n' "$hydra_sha" > "$hydra_vendor_dir/.hydra-pin"
printf 'Installed security skills at pin %s into %s\n' "$hydra_sha" "$hydra_vendor_dir"
printf 'Load skills lazily per docs/SECURITY-SKILLS.md; nothing was copied into .agents/skills/.\n'
