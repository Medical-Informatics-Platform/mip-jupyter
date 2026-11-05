# Notebook operator: hub side

The operator moved to the [mip repository](https://github.com/Medical-Informatics-Platform/mip):
source in `operator/`, design and contracts in `documentation/notebook-operator.md`.
Its image `hbpmip/mip-notebook-operator` is published from there. This repository
keeps the hub spawners that call it, and the single-user image it starts.

## Hub spawner

`JUPYTERHUB_SPAWNER` selects one (default `kubespawner` until the operator is
installed):

- `operator`: `docker/hub/notebook_spawner.py`, talks to the Kubernetes API.
- `operator-api`: `docker/hub/notebook_api_spawner.py`, talks to the spawn API
  with tornado's `AsyncHTTPClient`. Imports no Kubernetes client.

Both:

- `start()`: take `JUPYTERHUB_API_TOKEN` / `JPY_API_TOKEN` out of
  `get_env()`, create the `Notebook` (replacing a leftover one), create the
  token Secret `<name>-<uid>-token` owned by it, wait for `Running`, return
  `status.url`. On timeout delete the `Notebook`.
- `progress()`: yields `status.message` changes.
- `poll()`: `None` while `Pending`/`Running`, `1` when `Failed` or gone.
- `stop()`: delete the `Notebook` (foreground) and wait until it is gone.

`operator-api` maps these onto the endpoints above: `start()` is DELETE and
wait for 404 (60 s), PUT, then GET every second until `Running` with a `url`
or `Failed` (then DELETE and wait). It retries 429 (after `Retry-After`), 502,
503, 504 and no response, up to 6 attempts. Environment (madgik/mip chart):

| Variable | Value |
|---|---|
| `NOTEBOOK_API_URL` | `https://mip-notebook-spawn-api.mip-notebooks-system.svc.cluster.local` |
| `NOTEBOOK_API_TOKEN_FILE` | `/var/run/secrets/mip-notebook-operator/token`: projected, audience `mip-notebook-operator`, 3600 s; read on every request |
| `NOTEBOOK_API_CA_FILE` | `/var/run/secrets/mip-notebook-operator/ca.crt`: passed as `ca_certs`, loaded per connection |
| `POD_NAMESPACE` | downward API |

The hub pod sets `automountServiceAccountToken: false`.

`MIP_TOKEN` is no longer put in the pod env (the `env` rule rejects it). The
`mip` client fetches the first token from the hub `/api/platform-token`
endpoint, as it already did for refreshes.

## Testing

`docker/hub/test_notebook_spawner.py` and `test_notebook_api_spawner.py`, run
inside the hub image (CI does this after building it).
