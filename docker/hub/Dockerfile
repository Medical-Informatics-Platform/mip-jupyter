# syntax=docker/dockerfile:1.7
# Pinned by digest so pulls stay reproducible and CHP/Node stay in the base;
# bump the digest to pick up base fixes.
FROM jupyterhub/jupyterhub:5.5.4@sha256:d2b824f33fdbf5c5f8a9616be38cc77de624cf23c23a7b2fd441dd60ba50e87f

# Base tag lags on OS security fixes (e.g. openssl). /srv/venv has its own
# pip/setuptools/wheel, so the stale Ubuntu copies can go.
# nosemgrep: semgrep-rules.dockerfile.best-practice.avoid-apt-get-upgrade
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get purge -y python3-pip python3-pip-whl python3-setuptools python3-setuptools-whl python3-wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# The base ships configurable-http-proxy's tree with follow-redirects 1.16.0
# (CVE-2026-111755/111756). `npm update` moves it to the latest release within
# http-proxy-3's semver range; scripts are skipped so the base's postinstall is not re-run.
RUN npm --prefix /usr/local/lib update --ignore-scripts --no-audit --no-fund follow-redirects \
    && rm -rf /root/.npm

# oauthlib and Mako are JupyterHub dependencies, pinned past its versions for CVE fixes.
RUN pip install --no-cache-dir --disable-pip-version-check \
        jupyterhub-kubespawner==7.1.0 \
        oauthenticator==17.4.0 \
        oauthlib==4.0.0 \
        Mako==1.4.3

COPY docker/hub/jupyterhub_config.py \
     docker/hub/notebook_spawner.py \
     docker/hub/platform_token_service.py \
     docker/hub/platform_token_utils.py \
     /etc/jupyterhub/

ENV PYTHONPATH=/etc/jupyterhub \
    JUPYTERHUB_CONFIG=/etc/jupyterhub/jupyterhub_config.py

# Official image default; PVC in mip/deployment mounts here for the sqlite db.
WORKDIR /srv/jupyterhub
EXPOSE 8000
# Root, like the upstream image: the sqlite PVC from mip/deployment is root-owned.
# Going non-root needs a matching fsGroup/runAsUser there first.
# nosemgrep: dockerfile.security.missing-user.missing-user, semgrep-rules.dockerfile.security.missing-user
CMD ["jupyterhub", "-f", "/etc/jupyterhub/jupyterhub_config.py"]
