# syntax=docker/dockerfile:1.7
# Pinned by digest so pulls stay reproducible and CHP/Node stay in the base;
# bump the digest to pick up base fixes.
FROM jupyterhub/jupyterhub:5.5.2@sha256:1c38e6f0178c49b7b5fde7f119596a6fc8aecd66dc304403f5c1f25cfd843b5a

# Base tag lags on OS security fixes (e.g. openssl). /srv/venv has its own
# pip/setuptools/wheel, so the stale Ubuntu copies can go.
# nosemgrep: semgrep-rules.dockerfile.best-practice.avoid-apt-get-upgrade
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get purge -y python3-pip python3-pip-whl python3-setuptools python3-setuptools-whl python3-wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# HTTP2Shell (CVE-2026-111497): the system node that runs configurable-http-proxy
# links Ubuntu's libbrotli1, and the base (Ubuntu 24.04) ships 1.1.0-2build2, which is vulnerable.
# The upgrade above installs Ubuntu's fix, 1.1.0-2ubuntu0.1; fail the build if it did not.
RUN dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libbrotli1)" ge 1.1.0-2ubuntu0.1

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
