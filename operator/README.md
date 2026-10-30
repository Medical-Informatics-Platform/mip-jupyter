# mip-notebook-operator

Builds JupyterHub notebook pods from `Notebook` / `NotebookProfile` resources so
the hub needs no permission on pods or PVCs. With `--mode=spawn-api` the same
image serves the hubs' HTTPS spawn API, so they need no Kubernetes credential
at all. Design, RBAC and rollout:
[docs/notebook-operator.md](../docs/notebook-operator.md).

Scaffolded with Operator SDK (`go/v4` plugin).

```bash
make test                    # envtest controller and spawn API tests
make manifests generate      # after editing api/ or RBAC markers; commit the output
docker build -t hbpmip/mip-notebook-operator:<tag> .
```

CRDs: `config/crd/bases/`. Operator RBAC: `config/rbac/role.yaml` (generated).
Spawn API RBAC: `config/rbac/spawn_api_role.yaml` (hand-maintained; never give
it to the controller's account). Policy on the token Secrets: `config/policy/`.
The deployments live in `mip-infra-staging`. The controller (`--mode=controller`,
the default) needs `WATCH_NAMESPACES` (comma separated) and leader election
(`--leader-elect`). The spawn API (`--mode=spawn-api`) needs neither; it takes
`--spawn-api-bind-address`, `--tls-cert-dir`, `--health-probe-bind-address`,
and optionally `--metrics-bind-address` and `--spawn-api-rate-limit` /
`--spawn-api-rate-burst`.
