"""Who may use the hub: run with `python -m unittest test_platform_role` (no hub needed)."""

from __future__ import annotations

import base64
import json
import unittest

from platform_token_utils import has_platform_role


def token(claims: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


class HasPlatformRole(unittest.TestCase):
    def test_authorities_claim_counts(self) -> None:
        self.assertTrue(has_platform_role(token({"authorities": ["research_dataset_ds1"]}), "mippublic"))

    def test_this_clients_roles_count(self) -> None:
        claims = {"resource_access": {"mippublic": {"roles": ["research_dataset_ds1"]}}}
        self.assertTrue(has_platform_role(token(claims), "mippublic"))

    def test_another_clients_roles_do_not_count(self) -> None:
        claims = {"resource_access": {"other": {"roles": ["research_dataset_ds1"]}}}
        self.assertFalse(has_platform_role(token(claims), "mippublic"))

    def test_this_client_without_roles_is_refused(self) -> None:
        self.assertFalse(has_platform_role(token({"resource_access": {"mippublic": {}}}), "mippublic"))

    def test_realm_roles_do_not_count(self) -> None:
        self.assertFalse(has_platform_role(token({"realm_access": {"roles": ["admin"]}}), "mippublic"))

    def test_realm_user_without_roles_is_refused(self) -> None:
        self.assertFalse(has_platform_role(token({"sub": "alice", "authorities": []}), "mippublic"))

    def test_missing_or_malformed_token_is_refused(self) -> None:
        self.assertFalse(has_platform_role(None, "mippublic"))
        self.assertFalse(has_platform_role("not-a-jwt", "mippublic"))

    def test_malformed_resource_access_is_refused(self) -> None:
        self.assertFalse(has_platform_role(token({"resource_access": "x"}), "mippublic"))
        self.assertFalse(has_platform_role(token({"resource_access": {"mippublic": "x"}}), "mippublic"))


if __name__ == "__main__":
    unittest.main()
