# Notebook operator

JupyterHub no longer creates pods or PVCs. It creates a `Notebook` custom
resource; the MIP notebook operator (`operator/`, Operator SDK `go/v4`) turns it
into a pod and a PVC from a `NotebookProfile` the hub cannot edit.

## Why

With KubeSpawner the hub needed a Role with `pods`/`persistentvolumeclaims`
create/delete in every `federation-*` namespace. When Argo CD creates that
Role, RBAC escalation prevention forces the Argo application controller to hold
`pods: create` (and RBAC write) cluster-wide. A compromised hub could run any image in a
namespace that also holds the platform databases and Exareme workers.

After the switch:

| Component | Can create pods | How |
|---|---|---|
| JupyterHub | no | `notebooks` create/get/list/watch/delete, `secrets` create (Role applied out-of-band by an admin) |
| Argo CD controller | no | no RBAC write either; only syncs `NotebookProfile` |
| Notebook operator | yes, only in namespaces an admin bound | ClusterRole + per-namespace RoleBinding; no access to Secrets |

## Resources

API group `notebooks.mip.ebrains.eu/v1alpha1`, both namespaced.

### NotebookProfile

Shipped by the `madgik/mip` chart, synced by Argo CD. The hub has no access.

```yaml
spec:
  image: hbpmip/mip-jupyter:0.0.1_candidate
  imagePullPolicy: IfNotPresent
  resources: {requests: {cpu: 500m, memory: 1G}, limits: {cpu: "1", memory: 4G}}
  storage:
    storageClassName: ceph-corbo-cephfs
    size: 2Gi
    mountPath: /home/jovyan
    fixOwnership: true    # root init container chowns the volume to 1000:100 (provisioners that ignore fsGroup)
  nodeSelector: {}
  env:                    # static, non-secret
    - {name: PLATFORM_BACKEND_URL, value: http://platform-backend-service:8080/services}
```

The operator, not the profile, sets the security context: `runAsUser: 1000`,
`runAsGroup: 100`, `fsGroup: 100`, `runAsNonRoot`, seccomp `RuntimeDefault`,
all capabilities dropped, no privilege escalation, no service account token.
The notebook listens on port 8888.

### Notebook

Created by the hub per server.

```yaml
metadata: {name: jupyter-{user_server}}  # KubeSpawner's pod name ("safe" slugs)
spec:
  profile: default
  user: <hub user name>
  serverName: ""
  env: {JUPYTERHUB_SERVICE_PREFIX: /notebook/user/<user>/, ...}
status:
  phase: Pending | Running | Failed
  url: http://<pod ip>:8888
  message: <latest reason>
```

CRD validation (CEL, enforced by the API server):

- `spec` is immutable; a restart is delete + create.
- `env` keys match `^(JUPYTERHUB|JPY)_[A-Z0-9_]+$` and exclude
  `JUPYTERHUB_API_TOKEN` / `JPY_API_TOKEN`.
- Names start with `jupyter-` and are at most 57 characters.

The hub puts its API token in Secret `<notebook name>-<notebook uid>-token`
(key `token`, owned by the `Notebook`). The API server assigns the UID, so no
Secret that existed before the `Notebook` is ever mounted: not
`keycloak-credentials`, and not a token left by an earlier `Notebook` of the
same name. The hub can create Secrets but not overwrite them. The
ValidatingAdmissionPolicy in `operator/config/policy/hub-token-secrets.yaml`
admits only Opaque Secrets named and owned that way from the hub, so it cannot
create a `kubernetes.io/service-account-token` Secret, which the API server
would fill with another ServiceAccount's token, for a pod to mount. The
operator never reads Secrets.

## Operator

One Deployment in `mip-notebooks-system`, leader election on, watching only the
namespaces in `WATCH_NAMESPACES` (comma separated). Adding a federation means
adding it to that list and binding the ClusterRole there.

Reconcile of a `Notebook`:

1. Deleted: nothing to do. Pod and token Secret are owned by the `Notebook` and
   garbage collected.
2. Load the profile. Missing: `Failed`, retried every 30s.
3. Ensure PVC `claim-{user_server}`, KubeSpawner's name for the user's default
   server, so homes KubeSpawner created are reused. Never owned, updated or
   deleted, so home directories survive restarts.
4. Ensure pod (bare pod, owned by the `Notebook`). A pod that ends is not
   recreated; the hub sees `Failed` and the user starts again. Until the hub
   has created the token Secret the kubelet holds the pod in
   `CreateContainerConfigError`, reported as the message.
5. Status from the pod: `Running` + `url` when Ready, `Pending` with the waiting
   reason (`ImagePullBackOff`, `Unschedulable`, ...), `Failed` with the
   termination message.

Profile edits apply from the next start; running pods are not touched.

Operator RBAC (ClusterRole `mip-notebook-operator`, generated in
`operator/config/rbac/role.yaml`, bound per namespace): `pods` and
`persistentvolumeclaims` get/list/watch/create, `notebooks` and
`notebookprofiles` get/list/watch, `notebooks/status` get/update/patch. No
Secrets, no delete: garbage collection removes pods.

## Hub spawner

`docker/hub/notebook_spawner.py`, selected by `JUPYTERHUB_SPAWNER=operator`
(default `kubespawner` until the operator is installed).

- `start()`: take `JUPYTERHUB_API_TOKEN` / `JPY_API_TOKEN` out of
  `get_env()`, create the `Notebook` (replacing a leftover one), create the
  token Secret `<name>-<uid>-token` owned by it, wait for `Running`, return
  `status.url`. On timeout delete the `Notebook`.
- `progress()`: yields `status.message` changes.
- `poll()`: `None` while `Pending`/`Running`, `1` when `Failed` or gone.
- `stop()`: delete the `Notebook` (foreground) and wait until it is gone.

`MIP_TOKEN` is no longer put in the pod env (the `env` rule rejects it). The
`mip` client fetches the first token from the hub `/api/platform-token`
endpoint, as it already did for refreshes.

## Rollout

1. `mip-jupyter`: operator image, hub image with both spawners, client change.
2. `mip-infra-staging`: install CRDs + operator, the hub Secret policy
   (`operator/config/policy`, Kubernetes 1.30+), out-of-band operator and hub
   RBAC, whitelist `NotebookProfile` in the federation AppProject, Argo
   controller gets `notebookprofiles` write.
3. `madgik/mip` chart: `jupyterhub.spawner: operator` renders the profile;
   `jupyterhub.rbac.create: false` leaves the hub Role to the admin.
4. `mip-infra-staging`: drop `pods: create` and RBAC write from the Argo
   controller.

The operator and hub images of one commit go together: they must agree on the
token Secret name and the CRD. Upgrade the CRD and operator first, then the
hub, with no server running in operator mode in between.

## Testing

- Operator: `cd operator && make test` (envtest: CRD validation rules, hub
  Secret policy, profile missing, pod build, status mapping, KubeSpawner PVC
  names).
- Spawner: `docker/hub/test_notebook_spawner.py`, run inside the hub image
  (CI does this after building it).
- Staging: spawn, stop, restart the hub with a server running, and confirm
  `kubectl auth can-i create pods --as=system:serviceaccount:<ns>:jupyterhub`
  returns `no`.
