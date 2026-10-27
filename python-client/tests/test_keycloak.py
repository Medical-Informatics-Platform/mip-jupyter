"""Sign-in from your own computer: Keycloak device login, refresh, logout, and MIP_URL."""

import base64
import hashlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from mip import keycloak
from mip.exceptions import MipBackendError
from mip.exceptions import MipConfigurationError

MIP_URL = "https://mip.example"
ISSUER = "https://idp.example/realms/MIP"
OIDC = {
    "issuer": ISSUER,
    "device_authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth/device",
    "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
    "revocation_endpoint": f"{ISSUER}/protocol/openid-connect/revoke",
}
DEVICE = {
    "device_code": "dev-code",
    "user_code": "ABCD-EFGH",
    "verification_uri_complete": f"{ISSUER}/device?user_code=ABCD-EFGH",
    "interval": 5,
    "expires_in": 600,
}


def _resp(status, body=None):
    response = MagicMock(status_code=status)
    response.json.return_value = body if body is not None else {}
    return response


def _make_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("utf-8").rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode("utf-8")).decode("utf-8").rstrip("=")
    return f"{header}.{payload}.signature"


def _entry(refresh_token="r1"):
    return {
        "client_id": "mip-cli",
        "token_endpoint": OIDC["token_endpoint"],
        "revocation_endpoint": OIDC["revocation_endpoint"],
        "refresh_token": refresh_token,
    }


class _CredentialsTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name, "mip", "credentials.json")
        patcher = patch("mip.keycloak.CREDENTIALS_FILE", self.file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, data):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(data), encoding="utf-8")

    def read(self):
        return json.loads(self.file.read_text(encoding="utf-8"))


def _get(auth_config=None, oidc=None):
    def get(url, **kwargs):
        if url.endswith("/auth-config"):
            return auth_config or _resp(200, {"issuer": ISSUER, "clientId": "mip-cli"})
        if url == f"{ISSUER}/.well-known/openid-configuration":
            return oidc or _resp(200, OIDC)
        raise AssertionError(url)

    return get


@patch("mip.keycloak.requests.post")
@patch("mip.keycloak.requests.get")
class TestLogin(_CredentialsTestCase):
    def _login(self):
        shown, sleeps = [], []
        result = keycloak.login(MIP_URL, f"{MIP_URL}/services", show=shown.append, sleep=sleeps.append)
        return result, shown, sleeps

    def test_device_login_saves_refresh_token_only_for_you(self, get_mock, post_mock):
        get_mock.side_effect = _get()
        post_mock.side_effect = [
            _resp(200, DEVICE),
            _resp(400, {"error": "authorization_pending"}),
            _resp(400, {"error": "slow_down"}),
            _resp(200, {"access_token": "acc", "refresh_token": "r1"}),
        ]
        self.write({"https://other.example": _entry("other")})

        result, shown, sleeps = self._login()

        self.assertTrue(result["ok"])
        self.assertNotIn("r1", json.dumps(result))
        self.assertEqual(get_mock.call_args_list[0].args[0], f"{MIP_URL}/services/auth-config")
        self.assertIn(DEVICE["verification_uri_complete"], shown[0])
        self.assertIn("ABCD-EFGH", shown[0])
        self.assertEqual(sleeps, [5, 5, 10])
        device_request = post_mock.call_args_list[0]
        self.assertEqual(device_request.args[0], OIDC["device_authorization_endpoint"])
        self.assertEqual(device_request.kwargs["data"]["client_id"], "mip-cli")
        self.assertIn("offline_access", device_request.kwargs["data"]["scope"])
        self.assertEqual(device_request.kwargs["data"]["code_challenge_method"], "S256")
        poll = post_mock.call_args_list[1].kwargs["data"]
        self.assertEqual(poll["grant_type"], keycloak.DEVICE_GRANT)
        self.assertEqual(poll["device_code"], "dev-code")
        # PKCE: the challenge sent first is the SHA-256 of the verifier sent when polling.
        digest = hashlib.sha256(poll["code_verifier"].encode()).digest()
        self.assertEqual(
            base64.urlsafe_b64encode(digest).rstrip(b"=").decode(),
            device_request.kwargs["data"]["code_challenge"],
        )
        self.assertEqual(
            self.read(), {"https://other.example": _entry("other"), MIP_URL: _entry("r1"), "default": MIP_URL}
        )
        if os.name == "posix":
            self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)

    def test_portal_without_cli_client_says_so(self, get_mock, post_mock):
        # 404: no client configured; 401: a backend that predates /auth-config.
        for status in (404, 401):
            with self.subTest(status=status):
                get_mock.side_effect = _get(auth_config=_resp(status))
                with self.assertRaises(MipConfigurationError) as ctx:
                    self._login()
                self.assertIn("does not offer sign-in", str(ctx.exception))
        post_mock.assert_not_called()

    def test_untrusted_keycloak_is_refused(self, get_mock, post_mock):
        cases = {
            "plain http issuer": _get(auth_config=_resp(200, {"issuer": "http://idp.example/realms/MIP", "clientId": "c"})),
            "issuer mismatch": _get(oidc=_resp(200, {**OIDC, "issuer": "https://evil.example/realms/MIP"})),
            "plain http endpoint": _get(oidc=_resp(200, {**OIDC, "token_endpoint": "http://idp.example/token"})),
            "no device flow": _get(oidc=_resp(200, {**OIDC, "device_authorization_endpoint": None})),
        }
        for name, get in cases.items():
            with self.subTest(name):
                get_mock.side_effect = get
                with self.assertRaises((MipConfigurationError, MipBackendError)):
                    self._login()
        post_mock.assert_not_called()

    def test_denied_sign_in_saves_nothing(self, get_mock, post_mock):
        get_mock.side_effect = _get()
        post_mock.side_effect = [_resp(200, DEVICE), _resp(400, {"error": "access_denied"})]
        with self.assertRaises(MipBackendError) as ctx:
            self._login()
        self.assertIn("access_denied", str(ctx.exception))
        self.assertFalse(self.file.exists())


def _jwt(**claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"h.{body}.s"


@patch("mip.keycloak.requests.post")
@patch("mip.keycloak.requests.get")
class TestRelogin(_CredentialsTestCase):
    """Signing in again rotates: the sign-in it replaces is revoked at Keycloak."""

    def test_new_session_revokes_the_one_it_replaces(self, get_mock, post_mock):
        old = _jwt(sid="old-session")
        self.write({MIP_URL: _entry(old)})
        get_mock.side_effect = _get()
        post_mock.side_effect = [
            _resp(200, {"access_token": "acc", "refresh_token": _jwt(sid="new-session")}),
            _resp(200),
        ]

        result = keycloak.save_token(MIP_URL, f"{MIP_URL}/services", _jwt(sid="new-session"))

        self.assertTrue(result["previous_revoked"])
        revoke = post_mock.call_args_list[1]
        self.assertEqual(revoke.args[0], OIDC["revocation_endpoint"])
        self.assertEqual(revoke.kwargs["data"]["token"], old)
        self.assertEqual(self.read()[MIP_URL]["refresh_token"], _jwt(sid="new-session"))

    def test_same_session_pasted_again_is_not_revoked(self, get_mock, post_mock):
        self.write({MIP_URL: _entry(_jwt(sid="s1", n=1))})
        get_mock.side_effect = _get()
        post_mock.return_value = _resp(200, {"access_token": "acc", "refresh_token": _jwt(sid="s1", n=2)})

        result = keycloak.save_token(MIP_URL, f"{MIP_URL}/services", _jwt(sid="s1", n=1))

        self.assertNotIn("previous_revoked", result)
        self.assertEqual(post_mock.call_count, 1)  # only the check, no revocation

    def test_unreachable_keycloak_still_saves_the_new_sign_in(self, get_mock, post_mock):
        self.write({MIP_URL: _entry(_jwt(sid="old-session"))})
        get_mock.side_effect = _get()
        post_mock.side_effect = [
            _resp(200, {"access_token": "acc", "refresh_token": _jwt(sid="new-session")}),
            keycloak.requests.ConnectionError("down"),
        ]

        result = keycloak.save_token(MIP_URL, f"{MIP_URL}/services", _jwt(sid="new-session"))

        self.assertFalse(result["previous_revoked"])
        self.assertEqual(self.read()[MIP_URL]["refresh_token"], _jwt(sid="new-session"))


@patch("mip.keycloak.requests.post")
class TestAccessToken(_CredentialsTestCase):
    def test_refresh_returns_access_token_and_keeps_rotated_refresh_token(self, post_mock):
        self.write({MIP_URL: _entry("r1")})
        post_mock.return_value = _resp(200, {"access_token": "acc", "refresh_token": "r2"})

        self.assertEqual(keycloak.access_token(MIP_URL), "acc")

        self.assertEqual(post_mock.call_args.args[0], OIDC["token_endpoint"])
        self.assertEqual(
            post_mock.call_args.kwargs["data"],
            {"grant_type": "refresh_token", "refresh_token": "r1", "client_id": "mip-cli"},
        )
        self.assertEqual(self.read()[MIP_URL]["refresh_token"], "r2")

    def test_expired_sign_in_asks_for_mip_login(self, post_mock):
        self.write({MIP_URL: _entry()})
        post_mock.return_value = _resp(400, {"error": "invalid_grant"})
        with self.assertRaises(MipBackendError) as ctx:
            keycloak.access_token(MIP_URL)
        self.assertIn("mip login", str(ctx.exception))
        self.assertNotIn("r1", str(ctx.exception))

    def test_a_login_during_renewal_is_not_overwritten(self, post_mock):
        self.write({MIP_URL: _entry("r1")})

        def renew_while_another_process_logs_in(url, **kwargs):
            self.write({MIP_URL: _entry("new-login"), "default": MIP_URL})
            return _resp(200, {"access_token": "acc", "refresh_token": "r2"})

        post_mock.side_effect = renew_while_another_process_logs_in

        self.assertEqual(keycloak.access_token(MIP_URL), "acc")
        self.assertEqual(self.read()[MIP_URL]["refresh_token"], "new-login")

    def test_a_logout_during_renewal_is_not_undone(self, post_mock):
        self.write({MIP_URL: _entry("r1")})

        def renew_while_another_process_logs_out(url, **kwargs):
            self.write({})
            return _resp(200, {"access_token": "acc", "refresh_token": "r2"})

        post_mock.side_effect = renew_while_another_process_logs_out

        keycloak.access_token(MIP_URL)
        self.assertEqual(self.read(), {})

    @unittest.skipIf(keycloak.fcntl is None, "file locks are POSIX only")
    def test_credential_writes_wait_for_each_other(self, post_mock):
        entered = threading.Event()

        def second_writer():
            with keycloak._locked():
                entered.set()

        with keycloak._locked():
            thread = threading.Thread(target=second_writer)
            thread.start()
            self.assertFalse(entered.wait(0.2))
        thread.join(5)
        self.assertTrue(entered.is_set())

    def test_not_signed_in(self, post_mock):
        with self.assertRaises(MipConfigurationError):
            keycloak.access_token(MIP_URL)
        post_mock.assert_not_called()


@patch("mip.keycloak.requests.post")
class TestLogout(_CredentialsTestCase):
    def test_logout_revokes_and_forgets_only_this_portal(self, post_mock):
        self.write({MIP_URL: _entry("r1"), "https://other.example": _entry("other")})
        post_mock.return_value = _resp(200)

        self.assertEqual(keycloak.logout(MIP_URL, f"{MIP_URL}/services"), {"ok": True, "revoked": True})

        self.assertEqual(post_mock.call_args.args[0], OIDC["revocation_endpoint"])
        self.assertEqual(post_mock.call_args.kwargs["data"]["token"], "r1")
        self.assertEqual(self.read(), {"https://other.example": _entry("other")})

    def test_logout_forgets_the_remembered_portal(self, post_mock):
        self.write({MIP_URL: _entry(), "https://other.example": _entry("other"), "default": MIP_URL})
        post_mock.return_value = _resp(200)
        keycloak.logout(MIP_URL, f"{MIP_URL}/services")
        self.assertEqual(self.read(), {"https://other.example": _entry("other")})

    def test_logout_forgets_even_when_keycloak_is_unreachable(self, post_mock):
        self.write({MIP_URL: _entry()})
        post_mock.side_effect = keycloak.requests.ConnectionError("down")
        self.assertEqual(keycloak.logout(MIP_URL, f"{MIP_URL}/services"), {"ok": True, "revoked": False})
        self.assertEqual(self.read(), {})


@patch("mip.keycloak.requests.post")
@patch("mip.keycloak.requests.get")
class TestPortalToken(_CredentialsTestCase):
    """Tokens created on the portal's account page, for machines without a browser."""

    def test_pasted_token_is_checked_and_saved(self, get_mock, post_mock):
        get_mock.side_effect = _get()
        post_mock.return_value = _resp(200, {"access_token": "acc", "refresh_token": "rotated"})

        result = keycloak.save_token(MIP_URL, f"{MIP_URL}/services", " portal-token \n")

        self.assertTrue(result["ok"])
        self.assertEqual(post_mock.call_args.kwargs["data"]["refresh_token"], "portal-token")
        self.assertEqual(self.read(), {MIP_URL: _entry("rotated"), "default": MIP_URL})

    def test_rejected_token_is_not_saved(self, get_mock, post_mock):
        get_mock.side_effect = _get()
        post_mock.return_value = _resp(400, {"error": "invalid_grant"})
        with self.assertRaises(MipBackendError) as ctx:
            keycloak.save_token(MIP_URL, f"{MIP_URL}/services", "bad-token")
        self.assertIn("account page", str(ctx.exception))
        self.assertNotIn("bad-token", str(ctx.exception))
        self.assertFalse(self.file.exists())

    def test_env_token_renews_in_memory_without_writing_files(self, get_mock, post_mock):
        get_mock.side_effect = _get()
        post_mock.side_effect = [
            _resp(200, {"access_token": "acc1", "refresh_token": "r2"}),
            _resp(200, {"access_token": "acc2"}),
        ]
        refresh = keycloak.env_token_refresher(f"{MIP_URL}/services", "r1")

        self.assertEqual(refresh(), "acc1")
        self.assertEqual(refresh(), "acc2")

        sent = [call.kwargs["data"]["refresh_token"] for call in post_mock.call_args_list]
        self.assertEqual(sent, ["r1", "r2"])
        self.assertEqual(get_mock.call_count, 2)  # auth-config and discovery, once
        self.assertFalse(self.file.exists())

    def test_logout_also_revokes_the_env_token(self, get_mock, post_mock):
        get_mock.side_effect = _get()
        post_mock.return_value = _resp(200)
        self.write({MIP_URL: _entry("saved")})

        result = keycloak.logout(MIP_URL, f"{MIP_URL}/services", env_token="from-env")

        revoked = [call.kwargs["data"]["token"] for call in post_mock.call_args_list]
        self.assertEqual(revoked, ["saved", "from-env"])
        self.assertTrue(result["env_token_revoked"])
        self.assertIn("MIP_API_TOKEN", result["note"])
        self.assertEqual(self.read(), {})

    def test_logout_forgets_even_when_the_portal_is_unreachable(self, get_mock, post_mock):
        get_mock.side_effect = keycloak.requests.ConnectionError("down")
        post_mock.return_value = _resp(200)
        self.write({MIP_URL: _entry("saved")})

        result = keycloak.logout(MIP_URL, f"{MIP_URL}/services", env_token="from-env")

        self.assertEqual(self.read(), {})
        self.assertTrue(result["revoked"])
        self.assertFalse(result["env_token_revoked"])
        self.assertNotIn("from-env", json.dumps(result))

