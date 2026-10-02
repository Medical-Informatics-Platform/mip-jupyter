"""Unit tests for platform token helpers and the hub auth config."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch

from traitlets.config.loader import PyFileConfigLoader

from platform_token_service import fresh_access_token
from platform_token_utils import (
    decode_jwt_exp,
    normalize_cpu,
    normalize_memory,
    refresh_access_token,
    token_is_expired,
)


def _make_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("utf-8").rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": exp}).encode("utf-8")
    ).decode("utf-8").rstrip("=")
    return f"{header}.{payload}.signature"


class PlatformTokenUtilsTests(unittest.TestCase):
    def test_decode_jwt_exp(self):
        exp = int(time.time()) + 3600
        token = _make_jwt(exp)
        self.assertEqual(decode_jwt_exp(token), float(exp))

    def test_token_is_expired(self):
        expired = _make_jwt(int(time.time()) - 60)
        valid = _make_jwt(int(time.time()) + 3600)
        self.assertTrue(token_is_expired(expired))
        self.assertFalse(token_is_expired(valid))


class MemoryNormalizationTests(unittest.TestCase):
    def test_normalize_memory_converts_kubernetes_units(self):
        self.assertEqual(normalize_memory("1Gi"), "1G")
        self.assertEqual(normalize_memory("512Mi"), "512M")
        self.assertEqual(normalize_memory("2G"), "2G")


class CpuNormalizationTests(unittest.TestCase):
    def test_normalize_cpu_converts_kubernetes_millicores(self):
        self.assertEqual(normalize_cpu("500m"), 0.5)
        self.assertEqual(normalize_cpu("1"), 1.0)
        self.assertEqual(normalize_cpu("1000m"), 1.0)


class RefreshAccessTokenTests(unittest.TestCase):
    @patch("platform_token_utils.requests.post")
    def test_refresh_access_token_returns_new_token(self, post_mock):
        new_token = _make_jwt(int(time.time()) + 3600)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"access_token": new_token, "refresh_token": "new-refresh"}
        post_mock.return_value = response

        auth_state = {"refresh_token": "old-refresh", "access_token": _make_jwt(int(time.time()) - 60)}
        with patch.dict(
            os.environ,
            {"KEYCLOAK_CLIENT_ID": "client", "KEYCLOAK_CLIENT_SECRET": "secret"},
            clear=False,
        ):
            token = refresh_access_token(auth_state)

        self.assertEqual(token, new_token)
        self.assertEqual(auth_state["access_token"], new_token)
        self.assertEqual(auth_state["refresh_token"], "new-refresh")

    def test_refresh_access_token_without_refresh_token_returns_none(self):
        auth_state = {"access_token": _make_jwt(int(time.time()) - 60)}
        self.assertIsNone(refresh_access_token(auth_state))

    @patch("platform_token_utils.requests.post")
    def test_refresh_access_token_keycloak_failure_returns_none(self, post_mock):
        response = MagicMock()
        response.status_code = 400
        post_mock.return_value = response

        auth_state = {"refresh_token": "old-refresh"}
        with patch.dict(
            os.environ,
            {"KEYCLOAK_CLIENT_ID": "client", "KEYCLOAK_CLIENT_SECRET": "secret"},
            clear=False,
        ):
            self.assertIsNone(refresh_access_token(auth_state))


class FreshAccessTokenTests(unittest.TestCase):
    def test_concurrent_requests_refresh_once(self):
        state = {"access_token": _make_jwt(int(time.time()) - 60), "refresh_token": "old-refresh"}
        new_token = _make_jwt(int(time.time()) + 3600)

        class User:
            name = "alice"

            async def get_auth_state(self):
                return dict(state)

            async def save_auth_state(self, auth_state):
                state.update(auth_state)

        def refresh(auth_state):
            auth_state["access_token"] = new_token
            return new_token

        async def three_requests():
            return await asyncio.gather(*(fresh_access_token(User()) for _ in range(3)))

        with patch("platform_token_service.refresh_access_token", side_effect=refresh) as refresh_mock:
            tokens = asyncio.run(three_requests())

        self.assertEqual(tokens, [new_token] * 3)
        self.assertEqual(refresh_mock.call_count, 1)


class HubAuthConfigTests(unittest.TestCase):
    def _load_config(self, **env):
        with patch.dict(os.environ, env, clear=True):
            return PyFileConfigLoader(
                "jupyterhub_config.py", path=os.path.dirname(os.path.abspath(__file__))
            ).load_config()

    def test_missing_keycloak_client_id_fails_closed(self):
        with self.assertRaises(SystemExit):
            self._load_config()

    def test_dummy_auth_needs_explicit_opt_in(self):
        config = self._load_config(JUPYTERHUB_USE_DUMMY_AUTH="1")
        self.assertEqual(config.JupyterHub.authenticator_class, "jupyterhub.auth.DummyAuthenticator")

    def test_keycloak_client_id_selects_oauth(self):
        config = self._load_config(KEYCLOAK_CLIENT_ID="mip")
        self.assertEqual(
            config.JupyterHub.authenticator_class, "oauthenticator.generic.GenericOAuthenticator"
        )


if __name__ == "__main__":
    unittest.main()
