import os

from platform_token_service import PlatformTokenHandler, fresh_access_token
from platform_token_utils import normalize_cpu, normalize_memory


def _env(name, default=""):
    return os.environ.get(name, default)


def _env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_base_url(path):
    if not path:
        return "/notebook/"
    normalized = path if path.startswith("/") else f"/{path}"
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized


_notebook_base = _normalize_base_url(_env("JUPYTERHUB_BASE_PATH", "/notebook/")).rstrip("/")
# HubAuthenticated and other hub code read JUPYTERHUB_BASE_URL (not JUPYTERHUB_BASE_PATH).
os.environ.setdefault("JUPYTERHUB_BASE_URL", f"{_notebook_base}/")

# Served behind platform-ui nginx at /notebook/.
c.JupyterHub.bind_url = "http://:8000"
c.JupyterHub.base_url = f"{_notebook_base}/"
# hub_bind_url listens inside the hub pod; hub_connect_url is how servers reach the Hub API.
# Include base_url path — with base_url=/notebook/, the API is at /notebook/hub/api (not /hub/api).
_hub_api_host = _env("JUPYTERHUB_INTERNAL_HOST", "jupyterhub")
_hub_api_port = _env("JUPYTERHUB_HUB_API_PORT", "8081")
c.JupyterHub.hub_bind_url = f"http://:{_hub_api_port}"
c.JupyterHub.hub_connect_url = f"http://{_hub_api_host}:{_hub_api_port}{_notebook_base}/hub"
c.JupyterHub.tornado_settings = {
    "headers": {
        "Content-Security-Policy": "frame-ancestors 'self'",
    },
    # Allow platform-ui at /notebook to read _xsrf for Hub API calls.
    "xsrf_cookie_kwargs": {"path": f"{_notebook_base}/"},
}

# Session cookie behind platform-ui nginx / HTTPS reverse proxy.
_cookie_secure = _env_bool("JUPYTERHUB_COOKIE_SECURE", True)
c.JupyterHub.cookie_options = {
    "SameSite": "Lax",
    "Secure": _cookie_secure,
}

_keycloak_client_id = _env("KEYCLOAK_CLIENT_ID")
_use_dummy_auth = _env_bool("JUPYTERHUB_USE_DUMMY_AUTH", False)
# Dummy auth lets anyone in under any name, so it needs an explicit opt-in: a
# missing Keycloak secret must stop the hub, not open it.
if not _keycloak_client_id and not _use_dummy_auth:
    raise SystemExit(
        "KEYCLOAK_CLIENT_ID is not set. Set it, or JUPYTERHUB_USE_DUMMY_AUTH=1 for local testing."
    )
_use_keycloak = not _use_dummy_auth

_crypt_key = _env("JUPYTERHUB_CRYPT_KEY")
if _crypt_key:
    c.CryptKeeper.keys = [_crypt_key]

if _use_keycloak:
    _auth_url = _env("KEYCLOAK_AUTH_URL", "https://iam.ebrains.eu/auth/").rstrip("/")
    _realm = _env("KEYCLOAK_REALM", "MIP")
    _realm_base = f"{_auth_url}/realms/{_realm}"

    c.JupyterHub.authenticator_class = "oauthenticator.generic.GenericOAuthenticator"
    c.GenericOAuthenticator.client_id = _keycloak_client_id
    c.GenericOAuthenticator.client_secret = _env("KEYCLOAK_CLIENT_SECRET")
    c.GenericOAuthenticator.authorize_url = f"{_realm_base}/protocol/openid-connect/auth"
    c.GenericOAuthenticator.token_url = f"{_realm_base}/protocol/openid-connect/token"
    c.GenericOAuthenticator.userdata_url = f"{_realm_base}/protocol/openid-connect/userinfo"
    c.GenericOAuthenticator.username_claim = "preferred_username"
    c.GenericOAuthenticator.scope = ["openid", "profile", "email", "offline_access"]
    c.GenericOAuthenticator.allow_all = True
    c.GenericOAuthenticator.manage_groups = False
    c.GenericOAuthenticator.auto_login = _env_bool("JUPYTERHUB_AUTO_LOGIN", True)
    if _env_bool("JUPYTERHUB_OAUTH_PROMPT_NONE", False):
        c.GenericOAuthenticator.extra_authorize_params = {"prompt": "none"}
    c.GenericOAuthenticator.logout_redirect_url = _env(
        "JUPYTERHUB_LOGOUT_REDIRECT_URL", "/"
    )
else:
    c.JupyterHub.authenticator_class = "jupyterhub.auth.DummyAuthenticator"
    c.DummyAuthenticator.password = _env("JUPYTERHUB_DUMMY_PASSWORD", "")

c.Authenticator.enable_auth_state = True

# "operator": the hub only creates Notebook resources and the MIP notebook
# operator builds the pods (docs/notebook-operator.md). "kubespawner": the hub
# creates pods itself and needs a Role on pods/PVCs.
_spawner_mode = _env("JUPYTERHUB_SPAWNER", "kubespawner").strip().lower()
if _spawner_mode == "operator":
    c.JupyterHub.spawner_class = "notebook_spawner.NotebookSpawner"
    # Covers a cold pull of the ~700 MB notebook image.
    c.NotebookSpawner.start_timeout = 300
else:
    c.JupyterHub.spawner_class = "kubespawner.KubeSpawner"
c.KubeSpawner.image = _env("JUPYTER_SINGLEUSER_IMAGE", "hbpmip/mip-jupyter:dev")
c.KubeSpawner.image_pull_policy = _env("JUPYTER_IMAGE_PULL_POLICY", "Always")
c.KubeSpawner.namespace = _env("JUPYTERHUB_NAMESPACE", os.environ.get("POD_NAMESPACE", "default"))

# Pass platform backend URL to all spawned notebooks.
_spawner_env = {
    "PLATFORM_BACKEND_URL": _env(
        "PLATFORM_BACKEND_URL", "http://platform-backend-service:8080/services"
    ),
    "JUPYTER_TOKEN": _env("JUPYTER_SINGLEUSER_TOKEN", ""),
    "JUPYTERHUB_API_URL": f"http://{_hub_api_host}:{_hub_api_port}{_notebook_base}/hub/api",
}
# Forward only what is set; the notebook image applies Codex defaults (codex_bootstrap.py).
for _key in (
    "CODEX_VLLM_BASE_URL",
    "CODEX_VLLM_MODEL",
    "CODEX_REASONING_EFFORT",
    "CODEX_VLLM_PROVIDER",
    "CODEX_MODEL_CONTEXT_WINDOW",
    "CODEX_AUTO_COMPACT_TOKEN_LIMIT",
):
    if _value := _env(_key):
        _spawner_env[_key] = _value
c.KubeSpawner.environment = _spawner_env

# Pin user pods (and hostpath volumes) to the hub node when set, e.g. master=true.
_node_selector = _env("JUPYTER_NODE_SELECTOR")
if _node_selector:
    c.KubeSpawner.node_selector = {
        key.strip(): value.strip()
        for key, value in (pair.split("=", 1) for pair in _node_selector.split(",") if "=" in pair)
    }

# Persistence: storage_class/capacity alone do not mount a volume.
c.KubeSpawner.storage_pvc_ensure = _env_bool("JUPYTER_STORAGE_PVC_ENSURE", True)
c.KubeSpawner.storage_class = _env("JUPYTER_STORAGE_CLASS", "k8s-local-storage")
c.KubeSpawner.storage_capacity = _env("JUPYTER_STORAGE_CAPACITY", "2Gi")
if c.KubeSpawner.storage_pvc_ensure:
    c.KubeSpawner.volumes = [
        {
            "name": "home",
            "persistentVolumeClaim": {"claimName": "{pvc_name}"},
        }
    ]
    c.KubeSpawner.volume_mounts = [
        {
            "name": "home",
            "mountPath": "/home/jovyan",
        }
    ]
    # Hostpath PVCs are root-owned; chown once (skip the recursive walk when already owned).
    c.KubeSpawner.init_containers = [
        {
            "name": "fix-home-perm",
            "image": _env("JUPYTER_SINGLEUSER_IMAGE", "hbpmip/mip-jupyter:dev"),
            "command": [
                "sh",
                "-c",
                '[ "$(stat -c %u:%g /mnt/home)" = 1000:100 ] || chown -R 1000:100 /mnt/home; '
                "mkdir -p /mnt/home/work && chown 1000:100 /mnt/home/work",
            ],
            "volumeMounts": [{"name": "home", "mountPath": "/mnt/home"}],
            "securityContext": {"runAsUser": 0, "runAsGroup": 0},
        }
    ]

# Resource limits for spawned notebooks. Set JUPYTER_MEM_LIMIT=none to drop the cgroup cap.
c.KubeSpawner.cpu_limit = normalize_cpu(_env("JUPYTER_CPU_LIMIT", "1"))
c.KubeSpawner.cpu_guarantee = normalize_cpu(_env("JUPYTER_CPU_GUARANTEE", "500m"))
c.KubeSpawner.mem_guarantee = normalize_memory(_env("JUPYTER_MEM_GUARANTEE", "1G"))
_mem_limit = _env("JUPYTER_MEM_LIMIT", "4G")
if _mem_limit.strip().lower() not in {"", "0", "none", "unlimited"}:
    c.KubeSpawner.mem_limit = normalize_memory(_mem_limit)

# Security: ensure pods run as the jovyan user.
c.KubeSpawner.pod_security_context = {
    "fsGroup": 100,
    "runAsUser": 1000,
    "fsGroupChangePolicy": "OnRootMismatch",
}


async def inject_platform_token(spawner):
    """Inject platform-backend Bearer token into the single-user server environment."""
    token = await fresh_access_token(spawner.user)
    if not token and not _use_keycloak:
        # Dummy-auth hubs have no per-user token; Keycloak users never get the hub's.
        token = _env("MIP_TOKEN") or _env("PLATFORM_TOKEN")
    if token:
        spawner.environment["MIP_TOKEN"] = token


# With the operator the token is not put in the pod env; the mip client fetches
# it from /api/platform-token instead.
if _spawner_mode != "operator":
    c.Spawner.pre_spawn_hook = inject_platform_token

c.JupyterHub.extra_handlers = [
    (r"/api/platform-token", PlatformTokenHandler),
]
