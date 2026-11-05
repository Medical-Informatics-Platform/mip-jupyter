"""JupyterHub spawner that asks the MIP notebook spawn API for servers.

``operator-api`` mode: the hub holds no Kubernetes credential. It calls the
spawn API (``operator --mode=spawn-api``) over HTTPS with a projected token
whose audience the Kubernetes API server rejects; the spawn API creates the
``Notebook`` and its token Secret, the operator builds the pod. Nothing here
loads a Kubernetes client. See docs/notebook-operator.md.
"""

from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import quote

from jupyterhub.spawner import Spawner
from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest

from notebook_names import notebook_env, notebook_name

API_URL = os.environ.get("NOTEBOOK_API_URL", "https://mip-notebook-spawn-api.mip-notebooks-system.svc.cluster.local")
# Projected by the kubelet and rotated in place: read on every request.
TOKEN_FILE = os.environ.get("NOTEBOOK_API_TOKEN_FILE", "/var/run/secrets/mip-notebook-operator/token")
# Passed as ca_certs, which both tornado clients load per connection, so a
# renewed CA is picked up.
CA_FILE = os.environ.get("NOTEBOOK_API_CA_FILE", "/var/run/secrets/mip-notebook-operator/ca.crt")
NAMESPACE = os.environ.get("POD_NAMESPACE", "default")
POLL_INTERVAL = 1.0
DELETE_TIMEOUT = 60
# Rate limited, or a replica restarting (599: no response).
RETRY_CODES = (429, 502, 503, 504, 599)
MAX_ATTEMPTS = 6
MAX_BACKOFF = 30.0


def _read_token() -> str:
    # A small file on a tmpfs volume: reading it does not block the loop.
    with open(TOKEN_FILE) as f:
        return f.read().strip()


class SpawnAPIError(RuntimeError):
    def __init__(self, method: str, code: int, message: str):
        super().__init__(f"spawn API {method} answered {code}: {message}")
        self.code = code


class NotebookAPISpawner(Spawner):
    # The chart renders one NotebookProfile, "default".
    profile = "default"
    namespace = NAMESPACE

    _message = ""

    @property
    def notebook_name(self) -> str:
        return notebook_name(self.user.name, self.name)

    @property
    def _url(self) -> str:
        return f"{API_URL}/v1/namespaces/{quote(self.namespace, safe='')}/servers/{quote(self.notebook_name, safe='')}"

    async def _request(self, method: str, body: dict | None = None) -> tuple[int, dict]:
        for attempt in range(MAX_ATTEMPTS):
            headers = {"Authorization": f"Bearer {_read_token()}", "Accept": "application/json"}
            if body is not None:
                headers["Content-Type"] = "application/json"
            request = HTTPRequest(
                self._url,
                method=method,
                headers=headers,
                body=json.dumps(body) if body is not None else None,
                ca_certs=CA_FILE,
                validate_cert=True,
                connect_timeout=10,
                request_timeout=30,
            )
            retry_after = failure = None
            try:
                response = await AsyncHTTPClient().fetch(request, raise_error=False)
                code = response.code
                retry_after = response.headers.get("Retry-After")
            except (OSError, HTTPClientError) as e:
                # Connection refused, TLS failure, timeout: no response.
                code, response, failure = 599, None, str(e)
                self.log.warning("spawn API %s %s failed: %s", method, self.notebook_name, e)
            if code not in RETRY_CODES or attempt == MAX_ATTEMPTS - 1:
                break
            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                delay = 2.0**attempt
            await asyncio.sleep(min(max(delay, POLL_INTERVAL), MAX_BACKOFF))
        if response is None:
            return code, {"error": f"no response: {failure}"}
        try:
            data = json.loads(response.body or b"{}")
        except ValueError:
            data = {"error": (response.body or b"")[:200].decode(errors="replace")}
        return code, data

    async def _get(self) -> dict | None:
        code, data = await self._request("GET")
        if code == 404:
            return None
        if code != 200:
            raise SpawnAPIError("GET", code, data.get("error", ""))
        return data

    async def _delete_and_wait(self, timeout: float) -> None:
        code, data = await self._request("DELETE")
        if code not in (202, 404):
            raise SpawnAPIError("DELETE", code, data.get("error", ""))
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while await self._get() is not None:
            if loop.time() > deadline:
                raise TimeoutError(f"Notebook {self.notebook_name} was not deleted in {timeout:.0f}s")
            await asyncio.sleep(POLL_INTERVAL)

    async def start(self):
        env = self.get_env()
        # A leftover from a hub restart or a failed stop; no-op when absent.
        await self._delete_and_wait(DELETE_TIMEOUT)

        code, data = await self._request(
            "PUT",
            {
                "profile": self.profile,
                "user": self.user.name,
                "serverName": self.name or "",
                "env": notebook_env(env),
                # The spawn API puts it in the Notebook's token Secret.
                "apiToken": self.api_token,
            },
        )
        if code not in (200, 201):
            raise SpawnAPIError("PUT", code, data.get("error", ""))

        try:
            return await self._wait_running()
        except BaseException:
            await self._delete_and_wait(DELETE_TIMEOUT)
            raise

    async def _wait_running(self) -> str:
        while True:
            status = await self._get()
            if status is None:
                raise RuntimeError(f"Notebook {self.notebook_name} disappeared while starting")
            self._message = status.get("message") or self._message
            if status.get("phase") == "Running" and status.get("url"):
                return status["url"]
            if status.get("phase") == "Failed":
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
        status = await self._get()
        if status is None:
            return 1
        if status.get("phase") != "Failed":
            return None
        # Stopped by itself (File > Shut Down, a crash). JupyterHub calls stop() only for servers
        # poll() reports running, so the Notebook, its pod and its token Secret would stay until the
        # next start: delete it now, as KubeSpawner's delete_stopped_pods does. Not waited for;
        # start() waits for leftovers.
        if not status.get("deleting"):
            code, data = await self._request("DELETE")
            if code not in (202, 404):
                self.log.warning(
                    "spawn API DELETE of stopped %s failed: %s %s", self.notebook_name, code, data.get("error", "")
                )
        return 1

    async def stop(self, now=False):
        await self._delete_and_wait(DELETE_TIMEOUT)
