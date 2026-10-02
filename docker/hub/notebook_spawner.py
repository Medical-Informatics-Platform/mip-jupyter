"""JupyterHub spawner that asks the MIP notebook operator for servers.

The hub creates a ``Notebook`` custom resource and a token Secret owned by it;
the operator (``operator/`` in this repository) creates the pod and home PVC
from a ``NotebookProfile`` the hub cannot edit. The hub therefore needs no
permission on pods or PVCs. See docs/notebook-operator.md.
"""

from __future__ import annotations

import asyncio
import os
import re

from jupyterhub.spawner import Spawner
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.rest import ApiException
from kubespawner.slugs import multi_slug, safe_slug

GROUP = "notebooks.mip.ebrains.eu"
VERSION = "v1alpha1"
PLURAL = "notebooks"
TOKEN_ENV = ("JUPYTERHUB_API_TOKEN", "JPY_API_TOKEN")
# Must match the CRD validation rule on Notebook.spec.env.
ALLOWED_ENV = re.compile(r"^(JUPYTERHUB|JPY)_[A-Z0-9_]+$")
POLL_INTERVAL = 1.0
NAMESPACE = os.environ.get("POD_NAMESPACE", "default")
SLUG_MAX = 48


def notebook_env(env: dict[str, str]) -> dict[str, str]:
    """Keep only what a Notebook may carry; the token goes through the Secret."""
    return {k: v for k, v in env.items() if ALLOWED_ENV.match(k) and k not in TOKEN_ENV}


class NotebookSpawner(Spawner):
    # The chart renders one NotebookProfile, "default".
    profile = "default"
    namespace = NAMESPACE

    _api_client: client.ApiClient | None = None
    _message = ""

    @property
    def notebook_name(self) -> str:
        # KubeSpawner's pod name, jupyter-{user_server} ("safe" slugs): a name
        # kept as-is never contains "--", so it cannot equal an escaped one
        # ending in "---<hash>". At most 56 chars; the CRD allows 57.
        user = safe_slug(self.user.name, max_length=SLUG_MAX)
        server = safe_slug(self.name, max_length=SLUG_MAX) if self.name else ""
        if len(user) + len(server) + 2 > SLUG_MAX:
            return "jupyter-" + multi_slug([self.user.name, self.name or ""], max_length=SLUG_MAX)
        return "jupyter-" + (f"{user}--{server}" if server else user)

    async def _apis(self) -> tuple[client.CustomObjectsApi, client.CoreV1Api]:
        if NotebookSpawner._api_client is None:
            config.load_incluster_config()
            NotebookSpawner._api_client = client.ApiClient()
        api = NotebookSpawner._api_client
        return client.CustomObjectsApi(api), client.CoreV1Api(api)

    async def _get(self) -> dict | None:
        custom, _ = await self._apis()
        try:
            return await custom.get_namespaced_custom_object(
                GROUP, VERSION, self.namespace, PLURAL, self.notebook_name
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    async def _delete_and_wait(self, timeout: float) -> None:
        custom, _ = await self._apis()
        try:
            await custom.delete_namespaced_custom_object(
                GROUP, VERSION, self.namespace, PLURAL, self.notebook_name,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
        except ApiException as e:
            if e.status != 404:
                raise
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while await self._get() is not None:
            if loop.time() > deadline:
                raise TimeoutError(f"Notebook {self.notebook_name} was not deleted in {timeout:.0f}s")
            await asyncio.sleep(POLL_INTERVAL)

    async def _create_secret(self, owner: dict, token: str) -> None:
        _, core = await self._apis()
        meta = owner["metadata"]
        body = client.V1Secret(
            metadata=client.V1ObjectMeta(
                # The name the operator mounts. The UID keeps it clear of a
                # Secret the previous Notebook left for garbage collection.
                name=f"{meta['name']}-{meta['uid']}-token",
                namespace=self.namespace,
                owner_references=[
                    client.V1OwnerReference(
                        api_version=f"{GROUP}/{VERSION}", kind="Notebook", name=meta["name"], uid=meta["uid"]
                    )
                ],
            ),
            string_data={"token": token},
        )
        await core.create_namespaced_secret(self.namespace, body)

    async def start(self):
        env = self.get_env()
        # A leftover from a hub restart or a failed stop; no-op when absent.
        await self._delete_and_wait(60)

        custom, _ = await self._apis()
        notebook = await custom.create_namespaced_custom_object(
            GROUP, VERSION, self.namespace, PLURAL,
            {
                "apiVersion": f"{GROUP}/{VERSION}",
                "kind": "Notebook",
                "metadata": {"name": self.notebook_name, "namespace": self.namespace},
                "spec": {
                    "profile": self.profile,
                    "user": self.user.name,
                    "serverName": self.name or "",
                    "env": notebook_env(env),
                },
            },
        )
        await self._create_secret(notebook, self.api_token)

        try:
            return await self._wait_running()
        except BaseException:
            await self._delete_and_wait(60)
            raise

    async def _wait_running(self) -> str:
        while True:
            nb = await self._get()
            status = (nb or {}).get("status") or {}
            self._message = status.get("message") or self._message
            phase = status.get("phase")
            if nb is None:
                raise RuntimeError(f"Notebook {self.notebook_name} disappeared while starting")
            if phase == "Running" and status.get("url"):
                return status["url"]
            if phase == "Failed":
                raise RuntimeError(f"Notebook {self.notebook_name} failed: {self._message}")
            await asyncio.sleep(POLL_INTERVAL)

    async def progress(self):
        last = None
        while True:
            if self._message and self._message != last:
                last = self._message
                yield {"message": last}
            await asyncio.sleep(POLL_INTERVAL)

    async def poll(self):
        nb = await self._get()
        return None if nb and (nb.get("status") or {}).get("phase") != "Failed" else 1

    async def stop(self, now=False):
        await self._delete_and_wait(60)
