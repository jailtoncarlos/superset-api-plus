#!/usr/bin/env bash
# Runs the PR review appraisal facade (multi-llm-workflow review-appraisal) at the commit pinned in .mlw-pin.
#
# multi-llm-workflow is a private repository, so this public repository does not declare it in pyproject.toml or
# uv.lock (no CI job needs it). The pin is the full SHA of a commit of its origin/main, validated for this repository;
# changing it is a commit that edits .mlw-pin.
#
# The facade runs from a detached worktree of that commit, created once from the local clone (MLW_CLONE): the clone's
# own checkout is never moved. The command runs from the root of this repository, where the facade reads
# .review-appraisal.yaml.
#
# Usage:
#   bin/review-appraisal.sh collect jailtoncarlos/superset-api-plus --pr N --platform github-cli
# Environment:
#   MLW_CLONE    local clone of multi-llm-workflow (default: ~/workspace/multi-llm-workflow)
#   MLW_PIN_DIR  where the pinned worktrees live (default: ~/.cache/mlw-pin)
set -euo pipefail

root="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
pin="$(tr -d '[:space:]' < "$root/.mlw-pin")"
if [[ ! "$pin" =~ ^[0-9a-f]{40}$ ]]; then
  echo "review-appraisal: .mlw-pin must hold one full commit SHA (40 hex characters), found '$pin'" >&2
  exit 2
fi

clone="${MLW_CLONE:-$HOME/workspace/multi-llm-workflow}"
dir="${MLW_PIN_DIR:-$HOME/.cache/mlw-pin}/$pin"

if [[ ! -d "$dir" ]]; then
  if [[ ! -d "$clone/.git" && ! -f "$clone/.git" ]]; then
    echo "review-appraisal: no multi-llm-workflow clone at $clone (set MLW_CLONE)" >&2
    exit 2
  fi
  git -C "$clone" fetch --quiet origin
  mkdir -p "$(dirname "$dir")"
  git -C "$clone" worktree add --quiet --detach "$dir" "$pin"
fi

head="$(git -C "$dir" rev-parse HEAD)"
if [[ "$head" != "$pin" ]]; then
  echo "review-appraisal: the worktree $dir is at $head, expected $pin (.mlw-pin); remove it to recreate it" >&2
  exit 2
fi

cd "$root"
exec uv run --project "$dir" multi-llm-workflow review-appraisal "$@"
