import base64
import json
import os
import time
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from mip import Client
from mip.exceptions import MipBackendError
from mip.exceptions import MipConfigurationError
from mip.transport import Transport


def _make_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("utf-8").rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": exp}).encode("utf-8")
    ).decode("utf-8").rstrip("=")
    return f"{header}.{payload}.signature"


class TestClient(unittest.TestCase):
    def test_from_env_reads_mip_environment(self):
        with patch.dict(os.environ, {"MIP_BASE_URL": "http://backend/services", "MIP_TOKEN": "token"}, clear=True):
            client = Client.from_env()
        self.assertEqual(client._transport.base_url, "http://backend/services/")
        self.assertEqual(client._transport.token, "token")

    def test_from_env_reads_mip_token_with_platform_backend_url(self):
        with patch.dict(
            os.environ,
            {"PLATFORM_BACKEND_URL": "http://backend/services", "MIP_TOKEN": "mip-token"},
            clear=True,
        ):
            client = Client.from_env()
        self.assertEqual(client._transport.base_url, "http://backend/services/")
        self.assertEqual(client._transport.token, "mip-token")

    def test_from_env_prefers_platform_backend_url(self):
        with patch.dict(
            os.environ,
            {
                "PLATFORM_BACKEND_URL": "http://platform/services",
                "MIP_BASE_URL": "http://mip/services",
                "PLATFORM_TOKEN": "platform-token",
            },
            clear=True,
        ):
            client = Client.from_env()
        self.assertEqual(client._transport.base_url, "http://platform/services/")
        self.assertEqual(client._transport.token, "platform-token")

    def test_from_env_requires_base_url(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MipConfigurationError):
                Client.from_env()

    def test_client_does_not_expose_http_methods(self):
        client = Client("http://backend/services")
        self.assertFalse(hasattr(client, "get"))
        self.assertFalse(hasattr(client, "post"))

    def test_experiment_registry_maps_public_methods_to_backend_endpoints(self):
        client = Client("http://backend/services")
        transport = MagicMock()
        client._transport = transport
        transport.get.side_effect = [
            {"items": [{"id": "exp-1"}]},
            {"id": "exp-1", "status": "success"},
        ]

        registry = client.experiments()

        self.assertEqual(registry.list(), [{"id": "exp-1"}])
        self.assertEqual(registry.get("exp-1"), {"id": "exp-1", "status": "success"})
        self.assertIsNone(registry.delete("exp-1"))
        transport.get.assert_any_call("/experiments")
        transport.get.assert_any_call("/experiments/exp-1")
        transport.delete.assert_called_once_with("/experiments/exp-1")


class TestTransport(unittest.TestCase):
    @patch("mip.transport.requests.Session")
    def test_get_joins_base_url_and_returns_json(self, session_cls):
        response = MagicMock()
        response.status_code = 200
        response.content = b'{"ok": true}'
        response.json.return_value = {"ok": True}
        session = session_cls.return_value
        session.request.return_value = response

        transport = Transport("http://backend/services", token="token")
        payload = transport.get("/data-models", params={"q": "x"})

        self.assertEqual(payload, {"ok": True})
        session.headers.update.assert_called_with({"Authorization": "Bearer token"})
        session.request.assert_called_with(
            "GET",
            "http://backend/services/data-models",
            timeout=30.0,
            allow_redirects=False,
            params={"q": "x"},
        )

    @patch("mip.transport.requests.Session")
    def test_backend_error_is_wrapped(self, session_cls):
        response = MagicMock()
        response.status_code = 500
        response.text = "boom"
        response.json.side_effect = ValueError("not json")
        response.headers = {}
        session_cls.return_value.request.return_value = response

        transport = Transport("http://backend/services")
        with self.assertRaises(MipBackendError):
            transport.get("/data-models")

    @patch("mip.transport.requests.get")
    @patch("mip.transport.requests.Session")
    def test_refresh_token_via_jupyterhub_updates_token_and_env(self, session_cls, get_mock):
        expired = _make_jwt(int(time.time()) - 60)
        refreshed = _make_jwt(int(time.time()) + 3600)
        refresh_response = MagicMock()
        refresh_response.status_code = 200
        refresh_response.content = b'{"access_token":"' + refreshed.encode() + b'"}'
        refresh_response.json.return_value = {"access_token": refreshed}
        get_mock.return_value = refresh_response

        backend_response = MagicMock()
        backend_response.status_code = 200
        backend_response.content = b'{"ok": true}'
        backend_response.json.return_value = {"ok": True}
        session_cls.return_value.request.return_value = backend_response

        env = {
            "JUPYTERHUB_API_URL": "http://jupyterhub:8081/notebook/hub/api",
            "JUPYTERHUB_API_TOKEN": "hub-token",
            "MIP_TOKEN": expired,
        }
        with patch.dict(os.environ, env, clear=True):
            transport = Transport("http://backend/services", token=expired)
            payload = transport.get("/data-models")

            self.assertEqual(payload, {"ok": True})
            self.assertEqual(transport.token, refreshed)
            self.assertEqual(os.environ["MIP_TOKEN"], refreshed)

    @patch("mip.transport.requests.get")
    @patch("mip.transport.requests.Session")
    def test_missing_token_is_fetched_from_jupyterhub(self, session_cls, get_mock):
        fresh = _make_jwt(int(time.time()) + 3600)
        get_mock.return_value = MagicMock(
            status_code=200, content=b"{}", json=lambda: {"access_token": fresh}
        )
        backend_response = MagicMock(status_code=200, content=b'{"ok": true}')
        backend_response.json.return_value = {"ok": True}
        session_cls.return_value.request.return_value = backend_response

        env = {
            "JUPYTERHUB_API_URL": "http://jupyterhub:8081/notebook/hub/api",
            "JUPYTERHUB_API_TOKEN": "hub-token",
        }
        with patch.dict(os.environ, env, clear=True):
            transport = Transport("http://backend/services")
            self.assertEqual(transport.get("/data-models"), {"ok": True})
            self.assertEqual(transport.token, fresh)
            self.assertEqual(os.environ["MIP_TOKEN"], fresh)
            get_mock.assert_called_once()
            self.assertEqual(
                get_mock.call_args.args[0], "http://jupyterhub:8081/notebook/hub/api/platform-token"
            )

    @patch("mip.transport.requests.get")
    @patch("mip.transport.requests.Session")
    def test_expired_token_without_refresh_raises(self, session_cls, get_mock):
        expired = _make_jwt(int(time.time()) - 60)
        get_mock.return_value = MagicMock(status_code=401, content=b"", json=lambda: {})

        env = {
            "JUPYTERHUB_API_URL": "http://jupyterhub:8081/notebook/hub/api",
            "JUPYTERHUB_API_TOKEN": "hub-token",
            "MIP_TOKEN": expired,
        }
        with patch.dict(os.environ, env, clear=True):
            transport = Transport("http://backend/services", token=expired)
            with self.assertRaises(MipBackendError):
                transport.get("/data-models")


if __name__ == "__main__":
    unittest.main()
