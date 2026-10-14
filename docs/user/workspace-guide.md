# Workspace Guide

## Directory layout

```text
/home/jovyan/work/          (or workspace/ in local dev)
  Welcome.ipynb             Getting started
  examples/                 Canonical templates, read-only and updated centrally
  docs/                     User documentation (this folder)
  scratch/                  Your notebooks and experiments
```

Without the shared examples mount, `examples/` is absent or, in a home created by
an older image, a frozen copy that is no longer updated.

## Examples vs scratch

| Location | Use for |
|----------|---------|
| `examples/` | Reference notebooks, read-only and updated centrally. Read and learn from them. To adapt one, open it and use *File > Save Notebook As* into `scratch/`. |
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
