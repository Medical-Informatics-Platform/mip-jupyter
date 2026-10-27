# MIP Jupyter — User Documentation

Welcome to the Medical Informatics Platform (MIP) Jupyter workspace. The `mip` Python client is pre-installed and connects to the platform automatically when you launch notebooks from the MIP portal.

**Start here:** open [`Welcome.ipynb`](../Welcome.ipynb) and run all cells. Jupyter opens that notebook by default when you log in.

## Workspace map

| Path | Purpose |
|------|---------|
| [`Welcome.ipynb`](../Welcome.ipynb) | Guided getting-started walkthrough |
| [`examples/`](../examples/) | Canonical analysis notebooks, read-only and updated centrally; *Save Notebook As* into `scratch/` to adapt one |
| [`scratch/`](../scratch/) | Your notebooks and experiments |
| `docs/` (this folder) | MIP client help and troubleshooting |

## Guides

- [Quickstart](quickstart.md) — connect, discover data, run a simple analysis
- [How to choose the right API call](how-to-choose.md) — goal → method decision guide
- [API reference](api-reference.md) — filters, preprocessing, pipeline methods, results
- [Workspace guide](workspace-guide.md) — where to save work, examples vs scratch, kernel tips
- [Troubleshooting](troubleshooting.md) — connection and analysis errors
- [Use MIP from your own computer](remote-access.md) — `pip install mip-client`, then a token from the portal or `mip login`

## Typical workflow

1. Open `Welcome.ipynb` and run all cells to verify your connection.
2. Browse the catalog with `client.catalog()` to find data models and variables.
3. Copy an example into `scratch/` if you want to adapt it.
4. Build an `AnalysisSet` and `Pipeline`, then call algorithm methods directly on the pipeline.

## Connection

When you open notebooks from the MIP portal, authentication and platform access are configured for you.

See [Troubleshooting](troubleshooting.md) if `Client.from_env()` fails, or contact your platform administrator.
