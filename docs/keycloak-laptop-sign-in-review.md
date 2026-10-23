# Laptop sign-in with Keycloak: decisions, rollout and security review

Status on 2026-10-23. Companion documents: `keycloak-laptop-sign-in.md` (how it
works) and `keycloak-laptop-sign-in-plan.md` (the change list).

## 1. Decisions

1. **Keycloak is the only way in from users' own machines.** JupyterHub is out of
   the laptop path; it no longer hands Keycloak tokens to API tokens users create.
2. **One public Keycloak client per federation, `mip-cli-<federation>`.** No
   secret (a laptop cannot keep one), no roles of its own, no users assigned.
3. **Two ways to sign in, one credential.** The credential is a Keycloak offline
   refresh token:
   - *Portal*: "Create access token" on the account page signs in as the laptop
     client (authorization code with PKCE) and shows the token once. Users paste
     it into `mip login --token` or set `MIP_API_TOKEN`. Works for machines
     without a browser.
   - *Terminal*: `mip login` runs the device flow (with PKCE); the user approves
     in any browser.

   The `mip` client renews access tokens (5 minutes) by itself; users never refresh.
4. **Roles stay on the federation's platform client.** The laptop client has
   Full scope allowed, a copy of the platform client's `authorities` mapper, an
   audience mapper for the platform client, and the `roles` scope set to
   Optional. Its tokens therefore carry exactly the platform-client roles and
   are meant only for that federation.
5. **Backend.** A Bearer token must come from realm `MIP` and have been issued
   to this federation's own clients: `azp` = the platform client or the laptop
   client. `aud` is ignored. Roles come from `authorities` and that federation's
   client only. New public `GET /auth-config`
   tells the client and the portal which Keycloak client to use; the variable
   `KEYCLOAK_CLI_CLIENT_ID` (empty = off) switches the feature per federation.
6. **JupyterHub.** `/api/platform-token` answers only users' own notebook
   servers. The notebook path is otherwise unchanged.
7. **Where the credential lives.** `~/.config/mip/credentials.json` (mode 0600)
   or `MIP_API_TOKEN`. The portal never stores it.

Rejected:

| Option | Why not |
|---|---|
| Keep the JupyterHub broker | Laptop access depended on the hub and a recent Notebook visit |
| Broker in the backend | A central store of every user's long-lived sign-in, and more custom auth code |
| 30-day access tokens | Cannot be revoked; roles frozen for a month; lifetime is per client |
| Device flow on the existing confidential client | Needs its secret on every laptop, or a relay that makes the secret meaningless |
| One laptop client for all federations | Its tokens would be valid on every federation |

## 2. Current state

- **handson**: laptop sign-in switched off again on 2026-10-23 until every
  backend is upgraded (S1): `KEYCLOAK_CLI_CLIENT_ID` unset, test sign-ins revoked;
  the Keycloak client `mip-cli-handson` still exists (disable it to be sure).
  Before that, test images deployed (backend with `/auth-config`, portal with the
  token page, hub with the server-only rule), `KEYCLOAK_CLI_CLIENT_ID=mip-cli-handson`,
  client created in EBRAINS realm `MIP`. End-to-end test passed: device sign-in,
  portal token through `MIP_API_TOKEN`, data access, renewal after expiry in one
  process, `mip logout` and revocation. Laptop token claims: `azp=mip-cli-handson`,
  `aud=mippublic`, `authorities` = the three `mippublic` roles, no
  `resource_access` or `realm_access`.
- **Code**: uncommitted on `mip-jupyter` `feat/remote-access`, `platform-backend`
  and `platform-ui` `feat/remote-api-token`, `mip` `feat/keycloak-cli-client`.
- **Other federations**: backend `10.2.0`, hub `0.2.1`, no laptop client.

## 3. Rolling out to every federation

| Federation | Platform client | Portal |
|---|---|---|
| handson | `mippublic` | handson.hbpmip.link |
| mippublic | `mippublic` | hbpmip.link |
| dementia | `mipfed_dementia` | dementia.hbpmip.link |
| ecream | `mipfed_ecream` | ecream.hbpmip.link |
| epilepsy | `mipfed_epilepsy` | epilepsy.hbpmip.link |
| mentalhealth | `mipfed_mentalhealth` | mentalhealth.hbpmip.link |
| plovdiv | `mipfed_plovdiv` | plovdiv.local.hbpmip.link |
| repomse | `mipfed_repomse` | repomse.hbpmip.link |
| stroke | `mipfed_stroke` | stroke.hbpmip.link |

### Prerequisites, once, before any other federation gets a laptop client

| # | What | Why (section 4) |
|---|---|---|
| P1 | Release the backend with the token checks (issuer, `azp` = own clients) and deploy it to **every** federation, with `KEYCLOAK_CLI_CLIENT_ID` empty | S1, S2 |
| P2 | Give handson its own platform client (`mipfed_handson` exists) | S3 |
| P3 | Optional: set `roles` to Optional on every platform client (smaller tokens; not needed for safety once P1 is done) | S2 |
| P4 | Decide a realm-wide offline-session maximum | S4 |

P1 is safe on its own: the portal and JupyterHub use the platform client, so
they keep working; laptop sign-in stays off until step 5 below. One behaviour
change: users who have not accepted the terms of use get 403 from the API.

### Per federation `F` (platform client `P`, portal `U`)

Keycloak, realm `MIP`:
1. Create `mip-cli-F`: client authentication off; standard flow on; PKCE `S256`;
   device grant on; direct access grants and implicit flow off; consent off;
   valid redirect URI `U/account`; web origin `U`.
2. Client scopes: `roles` → Optional. Do not remove it from the client's tab:
   that dialog says "delete client scope".
3. Dedicated scope: User Client Role mapper (client `P`, claim `authorities`,
   multivalued, access token on), copied from `P`'s own; Audience mapper
   (included client `P`, access token on). Full scope allowed stays on.

Deployment (`mip` chart):

4. Backend, portal and hub images with this work.
5. `keycloak.cliClientId: mip-cli-F`.

Verify:

6. `GET U/services/auth-config` returns the client.
7. A token from each way in: `azp=mip-cli-F`, `aud=P` only, `authorities` =
   `P`'s roles only, no `resource_access`/`realm_access`.
8. Data loads; renewal works after 5 minutes; `mip logout` revokes.
9. The token is refused (401) by another federation's backend.
10. Notebooks still get tokens; a token made on `/hub/token` gets 403.

No upkeep afterwards: users and roles are managed on `P` as today.

## 4. Security review

| # | Finding | Severity | Status |
|---|---|---|---|
| S1 | **Released backends (10.2.0) accept any token of realm `MIP`** and take roles from `authorities`, `realm_access` and every client's `resource_access`. A token from one federation (portal, notebook or laptop) gets data on every other federation, under the role names it carries (e.g. `RESEARCH_DATASET_ALL`). Notebook users can already read their token, so this exists today; laptop sign-in makes tokens easier to carry around. From the code, not tested live. | **Critical** | Code ready. Open until P1 is deployed everywhere; laptop sign-in is off meanwhile. |
| S2 | **Platform-client tokens likely carry the audience of every client the user has roles on** (the `roles` scope is Default on them, and its audience mapper adds them; laptop tokens did this until `roles` became Optional). Even upgraded backends would then accept another federation's portal or notebook token, and trust its `authorities`, which hold the *issuing* federation's roles. | **High** | Fixed in code: the backend now accepts only `azp` = own clients and ignores `aud`. Takes effect with P1. |
| S3 | **handson and hbpmip.link share `mippublic`**, so their tokens are valid on each other. | Medium | Open. P2. |
| S4 | **Offline tokens have no hard expiry**: realm idle 30 days, no maximum. A leaked token works as long as it is used. | Medium | Open. P5; meanwhile `mip logout`, admin session revocation, or disabling `mip-cli-F` (kills all laptop sign-ins of that federation). |
| S5 | **Token on users' machines.** The file is plain text (mode 0600); `MIP_API_TOKEN` is inherited by child processes and AI assistants; users can paste it in the wrong place (happened in testing; that token was revoked). | Medium | Mitigated by docs and revocation. Option: OS keychain later. |
| S6 | **Device-code phishing**: an attacker starts a sign-in and sends a user the code. | Low–medium | Warning in `mip login` and docs; codes live 10 minutes. Option: switch the device grant off if portal tokens are enough. |
| S7 | **Token shown in the portal page**, readable by injected script while displayed. | Low | Shown once, not stored; PKCE, `state`, exact redirect URI. Option: Content-Security-Policy. |
| S8 | **Anyone can start a sign-in as the public client.** | Low | Tokens only after the user signs in; PKCE and exact redirect URI protect the code. |
| S9 | **Old hub API tokens** carrying `custom:mip-platform-token`. | Low | They no longer get platform tokens; remove the scope once they have expired. |
| S10 | `GET /auth-config` is public. | None | Issuer and a public client id are not secrets. |
| S11 | Audit. | Info | Laptop traffic is visible as `azp=mip-cli-F`. Whether Keycloak events are kept on EBRAINS is unknown. |

**Bottom line:** the laptop design itself holds up. Its tokens are narrow (one
audience, one federation's roles), revocable, and renewed by Keycloak. The
serious risks are in the existing platform: S1 and S2 let one federation's
tokens open another federation's data. The backend now closes both; deploy it
to every federation (P1) before switching laptop sign-in on anywhere.

## 5. Open items

- Commit, review and release the four branches; set `keycloak.cliClientId` per federation.
- On handson: re-test the notebook path (open the Notebook page once).
- After P1: test that a handson token gets 401 on another federation.
- Test that removing a dataset role takes effect within minutes.
