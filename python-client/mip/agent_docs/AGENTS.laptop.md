# MIP analysis workspace — agent instructions

This folder analyses data on a MIP federation with the `mip` Python client
(`pip install mip-client`). Data never leaves the federation: every result is an
aggregate computed there.

## Before writing analysis code

1. `mip env-status` — must say `"ready": true`. If not, ask the user to set up the
   connection themselves (see `mip guide 05-env-and-backend`).
2. `mip guide` — lists guide pages. Read the one that fits the task, narrowed with `--topic`:

| Task | Page |
|------|------|
| First steps | `01-onboarding` |
| Build an analysis | `02-analysis-workflow` |
| Client API (filters, preprocessing, results) | `03-mip-client-api` |
| Which algorithm, how to call it | `07-pipeline-algorithms` |
| Stroke analysis | `recipes/stroke-analysis` |

`mip guide --search TEXT` searches all pages.

## Discover data with the compact commands

Prefer these over printing large Python objects:

- `mip catalog` — data models you can access
- `mip data-model LABEL [--version V] [--variables]` — datasets and variables of one model
- `mip search-variables LABEL TEXT` — find variables
- `mip algorithms` — available algorithms

## Guide pages written for the hosted MIP notebook

Some pages mention `jupyter-mcp …` commands. On this computer use instead:

- `read-guide` → `mip guide`
- `mip-catalog-summary` / `mip-data-model-summary` / `mip-search-variables` / `mip-algorithm-summary`
  → `mip catalog` / `mip data-model` / `mip search-variables` / `mip algorithms`
- `scratch-*` and notebook commands → create and edit files and notebooks with your own tools

## Rules

- Never read, print, or log `MIP_TOKEN`, `PLATFORM_TOKEN`, or token files. Use
  `mip env-status` to check the connection.
- Never ask the user for a token.
- Everything you read goes to your provider. Read only the aggregate results the task
  needs, and do not upload them or send them to other services.
- Use variable and dataset labels exactly as `mip` returns them; do not invent codes.
