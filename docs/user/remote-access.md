# Use MIP from your own computer

You can run the `mip` client on your own computer. It acts as you, with the
same data access you have in the MIP portal.

## 1. Install the client

```bash
pip install mip-client
```

## 2. Create an API token

1. Sign in to the MIP portal and open the **Notebook** page once.
2. Open `https://<mip-host>/notebook/hub/token`.
3. In **Permissions**, enter `custom:mip-platform-token`. The token can then
   only fetch your MIP access; it cannot open or control your notebook server.
4. Choose an expiry, add a note (for example "laptop"), and click
   **Request new API token**.
5. Copy the token. It is shown only once. Treat it like a password.

## 3. Connect

```bash
export MIP_URL=https://<mip-host>
export MIP_API_TOKEN=<your token>
```

```python
import mip

client = mip.Client.from_env()
client.catalog()
```

Keep the token in environment variables. Do not put it in notebooks or scripts
you share or commit.

## Revoke a token

Open `https://<mip-host>/notebook/hub/token` and click **revoke** next to the
token. Do this when you no longer need it or if it may have leaked.

## Errors

- *JupyterHub rejected the API token*: the token is wrong, expired, revoked,
  or was created without the `custom:mip-platform-token` permission. Create a
  new one.
- *JupyterHub has no MIP platform token for you*: your portal sign-in has
  expired. Open the Notebook page in the MIP portal once, then retry.
- *Remote MIP URLs must use https://*: use the `https://` address of the portal.
