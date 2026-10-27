"""Unit tests for platform token helpers and the hub auth config."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jupyterhub import orm, roles, scopes
from jupyterhub.app import JupyterHub
from jupyterhub.utils import hash_token
from tornado import web
from traitlets.config.loader import PyFileConfigLoader

from platform_token_service import PlatformTokenHandler, fresh_access_token
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

    def test_servers_are_stopped_on_hub_restart_unless_disabled(self):
        self.assertTrue(self._load_config(JUPYTERHUB_USE_DUMMY_AUTH="1").JupyterHub.cleanup_servers)
        config = self._load_config(JUPYTERHUB_USE_DUMMY_AUTH="1", JUPYTERHUB_CLEANUP_SERVERS="false")
        self.assertFalse(config.JupyterHub.cleanup_servers)

    def test_idle_culler_runs_only_when_a_timeout_is_set(self):
        config = self._load_config(JUPYTERHUB_USE_DUMMY_AUTH="1")
        self.assertNotIn("services", config.JupyterHub)

        config = self._load_config(JUPYTERHUB_USE_DUMMY_AUTH="1", JUPYTERHUB_CULL_IDLE_TIMEOUT="3600")
        [service] = config.JupyterHub.services
        self.assertEqual(service["name"], "idle-culler")
        self.assertIn("--timeout=3600", service["command"])
        self.assertIn("--cull-every=600", service["command"])
        role = next(r for r in config.JupyterHub.load_roles if r["name"] == "idle-culler")
        self.assertEqual(role["services"], ["idle-culler"])
        self.assertIn("delete:servers", role["scopes"])


class LegacyScopeTests(unittest.TestCase):
    """Tokens issued while laptops used hub tokens carry custom:mip-platform-token."""

    def test_tokens_with_the_old_scope_still_resolve(self):
        with patch.dict(os.environ, {"JUPYTERHUB_USE_DUMMY_AUTH": "1"}, clear=True):
            app = JupyterHub(db_url="sqlite://")
            app.load_config_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jupyterhub_config.py"))
        app.init_db()
        app.authenticator = app.authenticator_class(parent=app)
        asyncio.run(app.init_role_creation())
        user = orm.User(name="alice")
        app.db.add(user)
        app.db.commit()
        roles.assign_default_roles(app.db, user)
        token = orm.APIToken.find(app.db, user.new_api_token(scopes=["read:users!user"]))
        token.scopes = ["custom:mip-platform-token"]
        app.db.commit()

        granted = scopes.parse_scopes(scopes.get_scopes_for(token))

        self.assertNotIn("custom:mip-platform-token", granted)


class PlatformTokenHandlerTests(unittest.TestCase):
    SERVER_TOKEN = "server-token"

    @staticmethod
    def _user(*server_tokens):
        # A server that never started has no OAuth client yet.
        user = MagicMock()
        user.orm_spawners = {
            str(i): SimpleNamespace(oauth_client=token and SimpleNamespace(secret=hash_token(token)))
            for i, token in enumerate(server_tokens)
        }
        return user

    @staticmethod
    def _get(user, raw_token):
        handler = MagicMock(current_user=user)
        handler.get_auth_token.return_value = raw_token
        asyncio.run(PlatformTokenHandler.get(handler))
        return handler

    @patch("platform_token_service.fresh_access_token")
    def test_server_token_gets_owner_access_token(self, fresh_mock):
        token = _make_jwt(int(time.time()) + 3600)
        fresh_mock.return_value = token
        user = self._user(None, "other-server", self.SERVER_TOKEN)
        handler = self._get(user, self.SERVER_TOKEN)
        fresh_mock.assert_called_once_with(user)
        handler.write.assert_called_once_with({"access_token": token})

    @patch("platform_token_service.fresh_access_token")
    def test_only_server_tokens_are_accepted(self, fresh_mock):
        user = self._user(self.SERVER_TOKEN)
        for name, raw in {"browser session": None, "token made on /hub/token": "laptop-token"}.items():
            with self.subTest(name), self.assertRaises(web.HTTPError) as ctx:
                self._get(user, raw)
            self.assertEqual(ctx.exception.status_code, 403)
        fresh_mock.assert_not_called()

    @patch("platform_token_service.fresh_access_token")
    def test_unauthenticated_is_rejected(self, fresh_mock):
        with self.assertRaises(web.HTTPError) as ctx:
            self._get(None, None)
        self.assertEqual(ctx.exception.status_code, 403)
        fresh_mock.assert_not_called()

    @patch("platform_token_service.fresh_access_token")
    def test_service_is_rejected(self, fresh_mock):
        with self.assertRaises(web.HTTPError) as ctx:
            self._get(orm.Service(name="svc"), "service-token")
        self.assertEqual(ctx.exception.status_code, 403)
        fresh_mock.assert_not_called()

    @patch("platform_token_service.fresh_access_token")
    def test_missing_platform_token_is_401(self, fresh_mock):
        fresh_mock.return_value = None
        with self.assertRaises(web.HTTPError) as ctx:
            self._get(self._user(self.SERVER_TOKEN), self.SERVER_TOKEN)
        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
