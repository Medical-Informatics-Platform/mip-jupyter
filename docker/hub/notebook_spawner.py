"""JupyterHub spawner that asks the MIP notebook operator for servers.

The hub creates a ``Notebook`` custom resource and a token Secret owned by it;
the operator (``operator/`` in this repository) creates the pod and home PVC
from a ``NotebookProfile`` the hub cannot edit. The hub therefore needs no
permission on pods or PVCs. See docs/notebook-operator.md.
"""

from __future__ import annotations

import asyncio
import os

from jupyterhub.spawner import Spawner
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.rest import ApiException

from notebook_names import notebook_env, notebook_name

GROUP = "notebooks.mip.ebrains.eu"
VERSION = "v1alpha1"
PLURAL = "notebooks"
POLL_INTERVAL = 1.0
NAMESPACE = os.environ.get("POD_NAMESPACE", "default")


class NotebookSpawner(Spawner):
    # The chart renders one NotebookProfile, "default".
    profile = "default"
    namespace = NAMESPACE

    _api_client: client.ApiClient | None = None
    _message = ""

    @property
    def notebook_name(self) -> str:
        return notebook_name(self.user.name, self.name)

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

    async def _delete(self) -> None:
        custom, _ = await self._apis()
        try:
            await custom.delete_namespaced_custom_object(
                GROUP, VERSION, self.namespace, PLURAL, self.notebook_name,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
        except ApiException as e:
            if e.status != 404:
                raise

    async def _delete_and_wait(self, timeout: float) -> None:
        await self._delete()
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
        if nb is None:
            return 1
        if (nb.get("status") or {}).get("phase") != "Failed":
            return None
        # Stopped by itself (File > Shut Down, a crash). JupyterHub calls stop() only for servers
        # poll() reports running, so the Notebook, its pod and its token Secret would stay until the
        # next start: delete it now, as KubeSpawner's delete_stopped_pods does. Not waited for;
        # start() waits for leftovers.
        if not (nb.get("metadata") or {}).get("deletionTimestamp"):
            try:
                await self._delete()
            except ApiException as e:
                self.log.warning("delete of stopped Notebook %s failed: %s", self.notebook_name, e.status)
        return 1

    async def stop(self, now=False):
        await self._delete_and_wait(60)
