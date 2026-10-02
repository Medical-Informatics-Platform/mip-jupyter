# mip-notebook-operator

Builds JupyterHub notebook pods from `Notebook` / `NotebookProfile` resources so
the hub needs no permission on pods or PVCs. Design, RBAC and rollout:
[docs/notebook-operator.md](../docs/notebook-operator.md).

Scaffolded with Operator SDK (`go/v4` plugin).

```bash
make test                    # envtest controller tests
make manifests generate      # after editing api/ or RBAC markers; commit the output
docker build -t hbpmip/mip-notebook-operator:<tag> .
```

CRDs: `config/crd/bases/`. Operator RBAC: `config/rbac/role.yaml`. Policy on
the hub's token Secrets: `config/policy/`. The deployment itself lives in
`mip-infra-staging`; it needs `WATCH_NAMESPACES` (comma separated) and leader
election (`--leader-elect`).
