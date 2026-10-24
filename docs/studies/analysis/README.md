---
title: "docs/studies/analysis/ — Analysis index"
type: readme
audience: human+ai-agent
updated: 2026-10-24
tldr: "Index of applied analyses: external findings mapped to defects, opportunities and decisions for this library."
tags: [studies, analysis, index]
related:
  - docs/studies/README.md
  - docs/studies/research/README.md
---

# docs/studies/analysis/ — Analysis index

| Date | Analysis | Summary | Based on |
|---|---|---|---|
| 2026-10-24 | [Impact of the client landscape on superset-api-plus](./2026-10-24-landscape-impact.md) | Defects confirmed in our code, prioritized improvement opportunities, design choices the landscape confirms, license decision | [research/2026-10-24-superset-client-landscape.md](../research/2026-10-24-superset-client-landscape.md) |
| 2026-10-24 | [Follow-up audit: layout rules, server error shapes and value sets](./2026-10-24-layout-errors-enums-audit.md) | Builder vs frontend `isValidChild` depth and size rules; error bodies of a live 6.1.0; library enums vs Superset's MCP service value sets | [research/2026-10-24-superset-client-landscape.md](../research/2026-10-24-superset-client-landscape.md) |
| 2026-10-24 | [Import Superset's classes or keep checked copies?](./2026-10-24-superset-as-dependency.md) | Blind review: keep own enums and models generated from and checked against the pinned Superset sources; never depend on `apache-superset` at runtime | [research/2026-10-24-superset-client-landscape.md](../research/2026-10-24-superset-client-landscape.md) |
