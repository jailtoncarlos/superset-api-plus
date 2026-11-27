#!/usr/bin/env bash
# Runs the PR review appraisal facade (multi-llm-workflow review-appraisal) at the commit pinned in .mlw-pin.
#
# multi-llm-workflow is a private repository, so this public repository does not declare it in pyproject.toml or
# uv.lock (no CI job needs it). The pin is the full SHA of a commit of its origin/main, validated for this repository;
# changing it is a commit that edits .mlw-pin. uvx installs that exact commit (cached per commit) and the facade runs
# from the root of this repository, where it reads .review-appraisal.yaml.
#
# Usage:
#   bin/review-appraisal.sh collect jailtoncarlos/superset-api-plus --pr N --platform github-cli
# Environment:
#   MLW_GIT_URL  git URL of multi-llm-workflow as uv accepts it (git+ssh://...), set locally: the repository is
#                private and its address is not recorded here.
set -euo pipefail

root="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
pin="$(tr -d '[:space:]' < "$root/.mlw-pin")"
if [[ ! "$pin" =~ ^[0-9a-f]{40}$ ]]; then
  echo "review-appraisal: .mlw-pin must hold one full commit SHA (40 hex characters), found '$pin'" >&2
  exit 2
fi
if [[ -z "${MLW_GIT_URL:-}" ]]; then
  echo "review-appraisal: set MLW_GIT_URL to the git URL of multi-llm-workflow as uv accepts it," >&2
  echo "  e.g. export MLW_GIT_URL=git+ssh://git@github.com/<owner>/multi-llm-workflow.git (in your shell profile)" >&2
  exit 2
fi

cd "$root"
exec uvx --from "$MLW_GIT_URL@$pin" multi-llm-workflow review-appraisal "$@"
