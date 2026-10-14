# Troubleshooting

## `Client.from_env()` fails or cannot connect

1. Confirm you opened Jupyter from the **MIP portal** (not a stale bookmark or direct URL).
2. Run the connection cells in `Welcome.ipynb` from the top after a fresh login.
3. If the problem persists, contact your **platform administrator** — they can verify your account and data access.

## Import errors (`import mip` fails)

The `mip` package is installed in the container image. If import fails, contact your platform operator.

## Analysis validation errors

- Some filter operators (for example `contains`, `starts_with`, `ends_with`) may not be available for every variable type.
- Check variable names with `dm.variables.search("...")` before building filters.
- Read the error message from the failed cell — it usually points to an invalid filter, variable, or algorithm choice.

## Notebook kernel issues

Restart the kernel after signing in again from the portal. If problems persist, restart the notebook server from JupyterHub or ask your administrator.

## Where to save work

- Use `scratch/` for your own notebooks and experiments.
- Canonical examples under `examples/` are read-only and updated centrally. To adapt one, open it and use *File > Save Notebook As* into `scratch/`.

See [Workspace guide](workspace-guide.md) for details.

## `examples/` is missing or out of date

The deployment does not mount the shared examples (for example KubeSpawner or
local runs). A home created by an older image keeps its real `examples/` folder
as a frozen copy that is no longer updated. Ask your platform administrator.

## Getting help

- Re-read [Quickstart](quickstart.md) and `Welcome.ipynb`.
- Use **Cohort Scout** in the Jupyter AI chat panel for notebook and workflow questions.
- Contact your platform administrator for access, connection, or data-model issues.
