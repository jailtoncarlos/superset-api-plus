---
title: "docs/studies/ — Curated studies"
type: readme
audience: human+ai-agent
updated: 2026-10-24
tldr: |
  Umbrella for curated studies. research/ holds descriptive studies grounded in
  external sources (other projects, Superset sources, docs); analysis/ turns
  those findings into decisions and work items for this library.
tags: [studies, research, analysis, index]
entry_point: true
---

# docs/studies/ — Curated studies

Knowledge base behind design decisions of `superset-api-plus`. It separates **research** (what exists
outside this repository, described with traceable sources) from **analysis** (what that means for this
library: gaps, defects and work items).

## Subdirectories

| Subdir | Purpose | Index |
|---|---|---|
| [research/](./research/README.md) | Descriptive studies of external sources: related projects, Superset behavior, ecosystem | [research/README.md](./research/README.md) |
| [analysis/](./analysis/README.md) | Applied analysis: findings mapped to files, defects and roadmap items of this library | [analysis/README.md](./analysis/README.md) |

## Classification criteria

| Belongs in `research/` if it… | Belongs in `analysis/` if it… |
|---|---|
| Describes external projects, specifications or source code | Proposes changes to this library's code, API or roadmap |
| Cites sources by URL and commit, with a cut-off date | Points to files of this repository and to the research it relies on |
| Does not define requirements for this library | Turns findings into defects, opportunities or decisions |

## Conventions

- File names: `YYYY-MM-DD-<topic>.md`, in English (see `AGENTS.md`, "Language").
- Front matter: `title`, `type` (`research` or `analysis`), `updated`, `cutoff`, `confidence`, `tldr`,
  `tags`, `related`.
- External code is cited as `owner/repo@<short sha>:path:line`, so references survive later commits.
- Studies describe public projects only; no institutional data (see `AGENTS.md`, "Security").
- A study is dated and is not kept in sync with later releases: write a new one instead of rewriting.
