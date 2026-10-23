# Use MIP from your own computer

You can run the `mip` client on your own computer or on a server. It acts as you,
with the same data access you have in the MIP portal. You sign in once; the
client then renews its access by itself, for up to 6 months.

## 1. Install the client

```bash
pip install mip-client
export MIP_URL=https://<mip-host>
```

(In Windows PowerShell, write `$env:MIP_URL = "https://<mip-host>"`.)

## 2. Sign in, one of two ways

**On a machine without a browser** (a server, a container, a script):

1. In the MIP portal, open your account page and click **Create access token**.
   Confirm with your MIP sign-in. The token is shown once: copy it.
2. On the machine, run `mip login --token` and paste it. It is saved in
   `~/.config/mip/credentials.json`, readable only by you.

In a script you can set `MIP_API_TOKEN` to the token instead, but every program
started from there, AI assistants included, can read environment variables.

**On a computer with a browser**, run `mip login`. It shows a link and a code.
Open the link in any browser, even on another device, and sign in. Check that the
page shows the same code, then approve. Never approve a code that someone else
sent you: whoever started that sign-in would get your access.

Either way, a sign-in lasts at most 6 months, and ends after 30 days without
use (the portal's operators set the exact limits). Then sign in again: signing
in again on a computer ends that computer's previous sign-in.

## 3. Connect

```python
import mip

client = mip.Client.from_env()
client.catalog()
```

## Use an AI assistant

The client ships a guide and a `mip` command that AI assistants (Claude Code,
Codex, Cursor, Copilot) can use. In the folder where you will work, run:

```bash
mip agent init
```

This writes `AGENTS.md` (and a `CLAUDE.md` that points to it). Open the folder in
your assistant and ask for the analysis. The assistant reads the guide with
`mip guide` and looks up data with `mip catalog`, `mip data-model`,
`mip search-variables` and `mip algorithms`.

The instructions tell the assistant never to read your sign-in file, but nothing
stops it: the file gives your full MIP data access until it expires or you sign
out. Whatever the assistant sees, including analysis results, goes to the
assistant's provider: check that your data-use terms allow this.

## Sign out

```bash
mip logout
```

This ends the sign-in at the MIP sign-in service and deletes it from your
computer. If `MIP_API_TOKEN` is set, that token is ended too; then remove it from
your environment. Do this when you no longer need it, or if the file may have leaked.

Without that computer, open your sign-in account (the link at the end of the
"Use MIP from your own computer" section of your MIP account page) and remove
"MIP command line" under Applications. This ends the sign-in of every computer.

## Errors

- *You are not signed in to ...*: run `mip login`, or `mip login --token` with a
  token from the account page.
- *Your MIP token has expired or was revoked*: create a new token, or run
  `mip login` again.
- *MIP_API_TOKEN needs MIP_URL*: set `MIP_URL` to the address of your portal.
- *This MIP portal does not offer sign-in from your own computer yet*: the
  portal's operators have not set it up. Ask them.
- *Sign-in failed (access_denied)* or *Sign-in timed out*: run `mip login`
  again and approve the code within a few minutes.
- *Remote MIP URLs must use https://*: use the `https://` address of the portal.
- *... must point at the same MIP portal*: `PLATFORM_BACKEND_URL` or
  `MIP_BASE_URL` is left from another setup. Unset it.
