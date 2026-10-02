"""Unit tests for NotebookSpawner. Needs jupyterhub + kubernetes_asyncio (hub image):

    docker run --rm -w /etc/jupyterhub mip-jupyterhub:<tag> python -m unittest test_notebook_spawner
"""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from kubernetes_asyncio.client.rest import ApiException

import notebook_spawner
from notebook_spawner import NotebookSpawner, notebook_env


class HelperTests(unittest.TestCase):
    def test_notebook_name_is_kubespawners_pod_name(self):
        def name(user, server=""):
            spawner = _spawner()
            spawner.user = SimpleNamespace(name=user)
            spawner.orm_spawner = SimpleNamespace(name=server)
            return spawner.notebook_name

        self.assertEqual(name("alice"), "jupyter-alice")
        self.assertEqual(name("alice", "x"), "jupyter-alice--x")
        # An escaped name never equals another user's plain one.
        self.assertEqual(name("john.doe"), "jupyter-john-doe---30f69670")
        self.assertEqual(name("john-doe-30f69670"), "jupyter-john-doe-30f69670")
        self.assertEqual(name("alice--x"), "jupyter-alice-x---2bbc534b")
        self.assertEqual(name("a" * 47), "jupyter-aaaaaaaaaaaaaaaaa--x---b191b19d")

    def test_notebook_env_drops_token_and_foreign_names(self):
        env = {
            "JUPYTERHUB_API_TOKEN": "t",
            "JPY_API_TOKEN": "t",
            "JUPYTERHUB_SERVICE_PREFIX": "/p/",
            "PATH": "/bin",
            "MIP_TOKEN": "secret",
        }
        self.assertEqual(notebook_env(env), {"JUPYTERHUB_SERVICE_PREFIX": "/p/"})


def _spawner():
    spawner = NotebookSpawner.__new__(NotebookSpawner)
    spawner.__dict__.update(
        {"_trait_values": {}, "_trait_notifiers": {}, "_trait_validators": {}, "_cross_validation_lock": False}
    )
    spawner.user = SimpleNamespace(name="alice")
    spawner.orm_spawner = SimpleNamespace(name="")
    spawner.namespace = "federation-a"
    spawner.profile = "default"
    spawner.log = MagicMock()
    spawner.api_token = "hub-token"
    spawner.get_env = lambda: {"JUPYTERHUB_API_TOKEN": "hub-token", "JUPYTERHUB_USER": "alice", "PATH": "/x"}
    return spawner


class StartStopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        patcher = patch.object(notebook_spawner, "POLL_INTERVAL", 0)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.custom = MagicMock()
        self.core = MagicMock()
        self.spawner = _spawner()
        self.spawner._apis = AsyncMock(return_value=(self.custom, self.core))

    async def test_start_creates_notebook_then_owned_secret_and_returns_url(self):
        created = {"metadata": {"name": "jupyter-alice", "uid": "uid-1"}}
        running = {"status": {"phase": "Running", "url": "http://10.0.0.7:8888", "message": "server ready"}}
        self.custom.get_namespaced_custom_object = AsyncMock(
            side_effect=[ApiException(status=404), {"status": {"phase": "Pending"}}, running]
        )
        self.custom.create_namespaced_custom_object = AsyncMock(return_value=created)
        self.custom.delete_namespaced_custom_object = AsyncMock(side_effect=ApiException(status=404))
        self.core.create_namespaced_secret = AsyncMock()

        url = await self.spawner.start()

        self.assertEqual(url, "http://10.0.0.7:8888")
        body = self.custom.create_namespaced_custom_object.call_args.args[4]
        self.assertEqual(body["spec"]["env"], {"JUPYTERHUB_USER": "alice"})
        secret = self.core.create_namespaced_secret.call_args.args[1]
        self.assertEqual(secret.metadata.name, "jupyter-alice-uid-1-token")
        self.assertEqual(secret.string_data, {"token": "hub-token"})
        self.assertEqual(secret.metadata.owner_references[0].uid, "uid-1")

    async def test_start_failure_deletes_notebook(self):
        failed = {"status": {"phase": "Failed", "message": "ImagePullBackOff"}}
        self.custom.get_namespaced_custom_object = AsyncMock(
            side_effect=[ApiException(status=404), failed, ApiException(status=404)]
        )
        self.custom.create_namespaced_custom_object = AsyncMock(
            return_value={"metadata": {"name": "jupyter-alice", "uid": "u"}}
        )
        self.custom.delete_namespaced_custom_object = AsyncMock()
        self.core.create_namespaced_secret = AsyncMock()

        with self.assertRaisesRegex(RuntimeError, "ImagePullBackOff"):
            await self.spawner.start()
        # Once for a possible leftover, once to clean up the failed start.
        self.assertEqual(self.custom.delete_namespaced_custom_object.await_count, 2)

    async def test_poll(self):
        self.custom.get_namespaced_custom_object = AsyncMock(
            side_effect=[{"status": {"phase": "Running"}}, {"status": {"phase": "Failed"}}, ApiException(status=404)]
        )
        self.assertIsNone(await self.spawner.poll())
        self.assertEqual(await self.spawner.poll(), 1)
        self.assertEqual(await self.spawner.poll(), 1)


if __name__ == "__main__":
    unittest.main()
