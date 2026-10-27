# Plan: long-lived access for the mip client through a public Keycloak client

## Goal

- A user gets a token from the platform UI and uses the `mip` Python client
  with it for 30+ days, also where no browser is available.
- The user never refreshes anything; the library renews access by itself.
- Keycloak stays the only identity provider. MIP stores no user credentials.

## Design

Each federation gets one **public** Keycloak client, `mip-cli-<federation>`, next to
its existing platform client (e.g. `mippublic`). It has no secret and no roles of
its own; its tokens carry the user's platform-client roles.

Two ways to get the credential (a Keycloak offline refresh token):

```text
 A. From the portal (any machine with a browser)
 1. Account page → Keycloak : sign in as mip-cli (PKCE, offline_access)
 2. Keycloak → browser      : offline refresh token, shown once, never stored
 3. User → headless env     : MIP_API_TOKEN=<token>  or  `mip login --token`

 B. From a terminal
 1. `mip login`             : prints a link and a code (device flow)
 2. User approves on any device with a browser
 3. Token saved in ~/.config/mip/credentials.json

 Every use (both)
 4. mip library → Keycloak  : refresh token → access token (minutes)
 5. mip library → backend   : Bearer access token
 6. backend                 : checks issuer, aud = platform client, roles
```

The notebook path is unchanged: JupyterHub keeps signing users in through the
platform client and handing tokens to their own servers only.

## 1. Keycloak, once per federation

Client `mip-cli-<federation>`:

| Setting | Value |
|---|---|
| Client authentication | Off (public) |
| Standard flow | On, PKCE method `S256` required (for way A) |
| Valid redirect URIs | `https://<portal>/account` |
| Web origins | `https://<portal>` (the browser calls the token endpoint) |
| OAuth 2.0 Device Authorization Grant | On (for way B) |
| Direct access grants, implicit flow, consent | Off |
| Full scope allowed | On (no per-role or per-user upkeep) |
| Client scopes | Set `roles` to Optional (removing it from the client's tab offers "delete client scope", too risky); keep `basic`, `profile`, `email`, `offline_access` |
| Mapper: User Client Role | Copy of the platform client's: Client ID = platform client, claim `authorities`, multivalued, in access token |
| Mapper: Audience | Included client audience = platform client, in access token |
| Advanced: offline session | Idle and max about 30–90 days |

Realm checks (no change expected): users have `offline_access` (default roles);
"Revoke Refresh Token" stays off, so a token kept in `MIP_API_TOKEN` survives
renewals; "Offline Session Max Limited" on only if a hard maximum is wanted.

Check: a `mip-cli` access token carries the platform-client roles in `authorities`
and has the platform client in `aud`.

Done for handson on 2026-10-23 (`mip-cli-handson`), except `roles` → Optional,
which is left to the realm admin.

## 2. platform-backend

Done (uncommitted):
- `GET /services/auth-config`, public: returns issuer and `KEYCLOAK_CLI_CLIENT_ID`,
  404 when unset (`AuthConfigAPI`, `PUBLIC_PATHS`, `application.yml`, tests,
  decision log, README).
- Branch commits already accept only tokens whose `azp` or `aud` is the platform
  client and read roles only from that client.

To do: nothing required. Optional: log `azp` on Bearer requests to tell laptop
traffic apart.

## 3. platform-ui

Done (uncommitted): account page shows the remote-access guide only when
`/auth-config` answers; JupyterHub token steps removed.

To do (way A, about 1–1.5 days), in `account-page.component.*` plus a small
helper, no new dependency:
1. "Create access token" button: read issuer and client id from `/auth-config`,
   fetch the issuer's discovery document, create a PKCE verifier and `state`
   (Web Crypto), keep them in `sessionStorage`, redirect to the authorize
   endpoint with `scope=openid offline_access` and `redirect_uri=<origin>/account`.
2. On return to `/account?code&state`: check `state`, exchange the code at the
   token endpoint with the verifier, remove `code` from the URL, clear
   `sessionStorage`.
3. Show the refresh token once with a copy button and both usage options
   (`MIP_API_TOKEN`, `mip login --token`). Never store it; drop it when leaving the page.
4. Keep the `mip login` (device flow) guide as the terminal alternative.
5. Tests: PKCE values, `state` mismatch refused, token request shape, token shown
   once and cleared, section hidden when `/auth-config` is 404.

No nginx or CSP change needed.

## 4. mip-jupyter: Python client

Done (uncommitted): `mip/keycloak.py` (device login, refresh, logout, credentials
file), `Client.from_env()` remote path with https and same-host checks,
`mip login`/`mip logout`, `env-status`, tests.

To do (about 0.5–1 day):
1. `mip login --token`: read the token hidden, look up the client and token
   endpoint through `/auth-config`, check it with one renewal, save it in the
   credentials file.
2. `MIP_API_TOKEN` (the refresh token) with `MIP_URL`: `from_env()` uses it ahead
   of the file, discovers the endpoints at first use, keeps rotated tokens in memory.
3. `mip logout` revokes whichever token `from_env()` would use.
4. Clear errors: "token expired or revoked: create a new one on the account page
   or run `mip login`".
5. Tests for all of the above; no live HTTP.
6. Docs: `docs/user/remote-access.md` (both ways), wiki `05-env-and-backend`,
   `AGENTS.laptop.md`, `expected_library.md`, READMEs.

## 5. mip-jupyter: JupyterHub

Done (uncommitted): `/api/platform-token` answers only users' own servers;
token-lifetime cap removed; `custom:mip-platform-token` kept defined so stored
tokens stay readable. Later: delete that scope once old tokens are gone.

## 6. Deployment (`mip` repo, not edited yet)

- `kubernetes/templates/platform-backend.yaml`: `KEYCLOAK_CLI_CLIENT_ID` from
  `.Values.keycloak.cliClientId`.
- `kubernetes/values.yaml`: `keycloak.cliClientId: ""` (empty = feature off).
- `dev/docker-compose.yml`, `dev/.env.example`: same variable.
- Deployment docs: per-federation steps.

## 7. Testing

Unit (per repo):
- mip-jupyter: `uv run pytest dev python-client/tests -q` and the hub tests in the
  hub image (see `.github/workflows/ci.yml`).
- platform-backend: `mvn test`.
- platform-ui: `npx ng test --watch=false`.

End to end on `federation-handson`:
1. Inspect a `mip-cli` token: only platform-client roles, right `aud`.
2. Way A: create a token in the portal, use it in a container with no browser:
   catalog and one analysis.
3. Way B: `mip login` with the device flow.
4. Access keeps working after the access token expires.
5. Remove a dataset role in Keycloak: gone within minutes.
6. `mip logout`, or ending the session in Keycloak: next call refused.
7. Handson token against another federation's backend: 401.
8. Notebook still gets its token; a token made on the hub page gets 403.
9. User who has not accepted the terms: 403.
10. From a typical headless environment: `iam.ebrains.eu` is reachable.

## 8. Rollout

Order per federation: Keycloak client → `KEYCLOAK_CLI_CLIENT_ID` on the backend →
portal → `mip-client` release → docs. Without the variable the feature stays
hidden, so federations can be enabled one at a time.

Rollback: unset `KEYCLOAK_CLI_CLIENT_ID` (guide hidden, `/auth-config` 404), or
disable the client in Keycloak (signs out every laptop of that federation at once).

Commits: one logical change per commit, on the existing branches
(`mip-jupyter` `feat/remote-access`, `platform-backend` and `platform-ui`
`feat/remote-api-token`). Handson currently runs test images built from the
uncommitted work.

## 9. Risks and open questions

1. **Keycloak access:** someone must create the client in EBRAINS realm `MIP`
   for each federation. Blocker if refused.
2. **Network:** headless environments must reach `iam.ebrains.eu`, not only the portal.
3. **Offline session limits** of the realm cap how long tokens live.
4. **Refresh-token rotation** must stay off for `MIP_API_TOKEN` to keep working.
5. **Token in the browser:** shown once and never stored, but readable by any
   script injected into the portal while displayed.
6. **Device-code phishing** (way B): users must never approve a code they did not start.
7. **Token in an environment variable** is inherited by every program, AI
   assistants included; the docs recommend the file.

## Progress

Built (uncommitted): sections 2, 3, 4 and 5, with tests and docs. Left: the
deployment chart (section 6, `mip` repo), the Keycloak client, and the
end-to-end test.

## Effort remaining (as planned)

| Part | Days |
|---|---|
| platform-ui (way A) | 1–1.5 |
| Python client (`--token`, `MIP_API_TOKEN`) | 0.5–1 |
| Deployment chart | 0.5 |
| Docs | 0.5 |
| End-to-end test | 0.5–1 |
| **Total** | **3–4**, plus Keycloak admin time |
