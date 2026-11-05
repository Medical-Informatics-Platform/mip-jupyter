# Signing in to MIP from your own computer

Users get a token from the portal's account page (or run `mip login` where a
browser is at hand). The `mip` client then has the same data access as the
portal and renews it by itself, for up to 6 months, or until 30 days without use
(Keycloak sets both limits). JupyterHub is not involved.
Cost: one extra Keycloak client per federation.

## Two clients per federation

| | Platform client (e.g. `mippublic`) | Laptop client (e.g. `mip-cli-handson`) |
|---|---|---|
| Used by | Portal, JupyterHub | Portal-created tokens, `mip login` |
| Secret | Yes, on the server | No |
| Data roles | Owns them; users are assigned here | None; borrows the platform client's |

The laptop client borrows the roles through "Full scope allowed" and a copy of
the platform client's role mapper (claim `authorities`). The backend accepts its
tokens because `azp` names this federation's laptop client
(`KEYCLOAK_CLI_CLIENT_ID`); it ignores `aud`, so the audience mapper in the setup
below is not what admits them. Roles are defined and assigned once.

## Flow

**Laptop, once, either way:**
- *Token from the portal* (no browser needed where the client runs): "Create
  access token" on the account page signs in as the laptop client and shows a
  token once (a Keycloak offline refresh token, not an access token); the user
  pastes it into `mip login --token` or `MIP_API_TOKEN`.
- *`mip login`*: asks the backend which Keycloak client to use
  (`/services/auth-config`), shows a link and a code, and the user approves in
  any browser.

Saved sign-ins go to `~/.config/mip/credentials.json`.

**Laptop, each use:** the client trades the sign-in for a short access token
carrying the user's roles and calls the backend with it. It renews the token by
itself. When the sign-in ends, `mip login` again. `mip logout` ends it early.

**Notebook (unchanged):** JupyterHub signs the user in through the platform
client and gives the notebook server a token, renewing it with the client's
secret. Tokens made on the JupyterHub token page no longer get MIP access.

## Problems

1. **One new client per existing client.** Each federation that wants laptop
   access needs its own laptop client. That means more Keycloak work, done by
   EBRAINS admins on their realm. Setup mistakes only show when a user signs
   in: no role mapper or no scope means no data.
2. **The existing client cannot be reused.** It is confidential: Keycloak
   wants its secret. A laptop cannot keep a secret, and shipping it to every
   user lets anyone act as the portal. Device sign-in is also off on
   `mippublic` today.
3. **One shared laptop client is not safe.** Every backend would have to accept
   its `azp`, so a laptop token would work on all of them. Access must never
   cross federations.
4. **Smaller points.** Session length is set in Keycloak, not in MIP. Revoking
   without the laptop needs the Keycloak account console or an admin. Users
   must never approve a code someone else sent them (device-code phishing).

## Alternative: relay through the backend

Switch on device sign-in on the existing platform client and let each backend
relay the sign-in with the secret it already holds. No new clients and no
mappers, but about three more backend endpoints, the backend in the sign-in
path, and laptop traffic indistinguishable from the portal's. Worth
reconsidering if creating clients per federation proves hard.

## Per-federation setup

1. Keycloak: create `mip-cli-<federation>`: public, standard flow on with PKCE
   S256 (redirect URI `<portal>/account`, web origin `<portal>`), device grant on,
   Full scope allowed, default `roles` scope replaced by a User Client Role mapper
   for the platform client, audience mapper to the platform client,
   `offline_access`, Client Offline Session Max 180 days (full list in the `mip`
   repository, `deployment/kubernetes/README.md`).
2. Backend: set `KEYCLOAK_CLI_CLIENT_ID=mip-cli-<federation>`.

## Status

Client, hub, backend and portal are on `master` of their repositories. The chart
setting `keycloak.cliClientId` is on `mip` branch
`combined/keycloak-cli-and-jupyterhub-spawner`, not yet on `master`. Rollout state
per federation: `keycloak-laptop-sign-in-review.md`.
