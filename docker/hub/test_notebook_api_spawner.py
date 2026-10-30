"""Unit tests for NotebookAPISpawner. Needs jupyterhub + tornado (hub image):

    docker run --rm -w /etc/jupyterhub mip-jupyterhub:<tag> python -m unittest test_notebook_api_spawner
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import notebook_api_spawner
from notebook_api_spawner import NotebookAPISpawner, SpawnAPIError

URL = "https://spawn-api.test/v1/namespaces/federation-a/servers/jupyter-alice"


def _response(code, body=None, headers=None):
    return SimpleNamespace(code=code, body=json.dumps(body or {}).encode(), headers=headers or {})


def _write(path, text):
    with open(path, "w") as f:
        f.write(text)


def _spawner():
    spawner = NotebookAPISpawner.__new__(NotebookAPISpawner)
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


class ImportTests(unittest.TestCase):
    def test_loads_no_kubernetes_client(self):
        code = (
            "import sys, notebook_api_spawner; "
            "bad = [m for m in sys.modules if m.split('.')[0] in ('kubernetes', 'kubernetes_asyncio', 'kubespawner')]; "
            "print(bad); sys.exit(1 if bad else 0)"
        )
        here = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run([sys.executable, "-c", code], cwd=here, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_notebook_name_matches_the_operator_spawner(self):
        spawner = _spawner()
        spawner.user = SimpleNamespace(name="john.doe")
        spawner.orm_spawner = SimpleNamespace(name="x")
        self.assertEqual(spawner.notebook_name, "jupyter-john-doe---30f69670--x")


class SpawnAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        fd, self.token_file = tempfile.mkstemp()
        os.write(fd, b"projected-1\n")
        os.close(fd)
        self.addCleanup(os.unlink, self.token_file)
        for name, value in {
            "POLL_INTERVAL": 0,
            "API_URL": "https://spawn-api.test",
            "TOKEN_FILE": self.token_file,
            "CA_FILE": "/ca.crt",
        }.items():
            patcher = patch.object(notebook_api_spawner, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.sleep = AsyncMock()
        patcher = patch.object(notebook_api_spawner.asyncio, "sleep", self.sleep)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.fetch = AsyncMock()
        client = MagicMock()
        client.return_value.fetch = self.fetch
        patcher = patch.object(notebook_api_spawner, "AsyncHTTPClient", client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.spawner = _spawner()

    def calls(self):
        return [(c.args[0].method, c.args[0].url) for c in self.fetch.await_args_list]

    async def test_start_deletes_leftover_puts_and_waits_for_running(self):
        self.fetch.side_effect = [
            _response(404),  # DELETE: nothing left over
            _response(404),  # GET: gone
            _response(201, {"phase": ""}),
            _response(200, {"phase": "Pending", "message": "ImagePulling"}),
            _response(200, {"phase": "Running", "url": "http://10.0.0.7:8888", "message": "server ready"}),
        ]

        url = await self.spawner.start()

        self.assertEqual(url, "http://10.0.0.7:8888")
        self.assertEqual(self.calls(), [("DELETE", URL), ("GET", URL), ("PUT", URL), ("GET", URL), ("GET", URL)])
        put = self.fetch.await_args_list[2].args[0]
        self.assertEqual(
            json.loads(put.body),
            {
                "profile": "default",
                "user": "alice",
                "serverName": "",
                "env": {"JUPYTERHUB_USER": "alice"},
                "apiToken": "hub-token",
            },
        )
        self.assertEqual(put.headers["Authorization"], "Bearer projected-1")
        self.assertEqual(put.ca_certs, "/ca.crt")
        self.assertTrue(put.validate_cert)

    async def test_reads_the_rotated_token_on_every_request(self):
        self.fetch.side_effect = [_response(200, {"phase": "Running"}), _response(200, {"phase": "Running"})]
        await self.spawner.poll()
        _write(self.token_file, "projected-2")
        await self.spawner.poll()
        tokens = [c.args[0].headers["Authorization"] for c in self.fetch.await_args_list]
        self.assertEqual(tokens, ["Bearer projected-1", "Bearer projected-2"])

    async def test_start_failure_deletes_and_waits(self):
        self.fetch.side_effect = [
            _response(404),
            _response(404),
            _response(201),
            _response(200, {"phase": "Failed", "message": "ImagePullBackOff"}),
            _response(202),
            _response(200, {"phase": "Failed", "deleting": True}),
            _response(404),
        ]
        with self.assertRaisesRegex(RuntimeError, "ImagePullBackOff"):
            await self.spawner.start()
        methods = [m for m, _ in self.calls()]
        self.assertEqual(methods, ["DELETE", "GET", "PUT", "GET", "DELETE", "GET", "GET"])

    async def test_put_conflict_is_an_error(self):
        self.fetch.side_effect = [_response(404), _response(404), _response(409, {"error": "is terminating"})]
        with self.assertRaisesRegex(SpawnAPIError, "409: is terminating"):
            await self.spawner.start()

    async def test_backs_off_on_429_using_retry_after(self):
        self.fetch.side_effect = [
            _response(429, {"error": "too many requests"}, {"Retry-After": "3"}),
            _response(429, {"error": "too many requests"}),
            _response(200, {"phase": "Running"}),
        ]
        self.assertIsNone(await self.spawner.poll())
        self.assertEqual([c.args[0] for c in self.sleep.await_args_list], [3.0, 2.0])

    async def test_retries_when_there_is_no_response(self):
        self.fetch.side_effect = [ConnectionRefusedError(), _response(404)]
        self.assertEqual(await self.spawner.poll(), 1)
        self.assertEqual(self.fetch.await_count, 2)

    async def test_gives_up_after_max_attempts(self):
        self.fetch.side_effect = [_response(503, {"error": "cannot verify the token"})] * notebook_api_spawner.MAX_ATTEMPTS
        with self.assertRaisesRegex(SpawnAPIError, "503"):
            await self.spawner.poll()

    async def test_poll(self):
        self.fetch.side_effect = [
            _response(200, {"phase": "Running"}),
            _response(200, {"phase": "Pending"}),
            _response(200, {"phase": "Failed"}),
            _response(404),
        ]
        self.assertIsNone(await self.spawner.poll())
        self.assertIsNone(await self.spawner.poll())
        self.assertEqual(await self.spawner.poll(), 1)
        self.assertEqual(await self.spawner.poll(), 1)

    async def test_stop_deletes_and_waits_until_gone(self):
        self.fetch.side_effect = [_response(202), _response(200, {"deleting": True}), _response(404)]
        await self.spawner.stop()
        self.assertEqual([m for m, _ in self.calls()], ["DELETE", "GET", "GET"])

    async def test_unauthorized_is_not_retried(self):
        self.fetch.side_effect = [_response(401, {"error": "invalid token"})]
        with self.assertRaisesRegex(SpawnAPIError, "401: invalid token"):
            await self.spawner.stop()
        self.assertEqual(self.fetch.await_count, 1)


if __name__ == "__main__":
    unittest.main()
