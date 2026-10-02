# Workspace Guide

## Directory layout

```text
/home/jovyan/work/          (or workspace/ in local dev)
  Welcome.ipynb             Getting started
  examples/                 Canonical templates — copy before editing
  docs/                     User documentation (this folder)
  scratch/                  Your notebooks and experiments
```

## Examples vs scratch

| Location | Use for |
|----------|---------|
| `examples/` | Reference notebooks shipped with the platform. Read and learn from them. Copy into `scratch/` before making changes. |
| `scratch/` | Your own analysis work. Safe to create, edit, and delete freely. |

Create new notebooks in `scratch/` unless your team has a different shared location.

## Saving and organizing work

- Use descriptive notebook names: `scratch/cohort_age_distribution.ipynb`.
- Keep exploratory drafts in `scratch/`; promote polished analyses by sharing with your team outside Jupyter if needed.
- Your `scratch/` content persists across sessions but may be subject to platform storage policies — check with your operator.

## Kernel tips

- **Restart kernel** after signing in again or when your administrator updates the workspace image.
- **Run All** from the top when you change filters, variables, or preprocessing — downstream cells depend on earlier definitions.
- Large federated analyses can take time to complete.

## What is not in this workspace

- `mip` Python client source — installed as a package, not editable here.
- Platform deployment settings — managed by your operator.

## Related docs

- [Quickstart](quickstart.md)
- [API reference](api-reference.md)
- [Troubleshooting](troubleshooting.md)
