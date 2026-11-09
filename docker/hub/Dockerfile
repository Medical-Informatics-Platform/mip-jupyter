# syntax=docker/dockerfile:1.7
# Pinned by digest so pulls stay reproducible and CHP/Node stay in the base;
# bump the digest to pick up base fixes.
FROM jupyterhub/jupyterhub:6.1.1-7@sha256:48973496688583afca1c29571c7e69849ed9b9ffb74874af29b2c87e787aa8c6

# 6.1.1-7 ships pebble 1.33.2 built with Go 1.27.3 (stdlib CVE-2026-111943 and
# the 1.27.2 set), oauthlib 4.0.1, tornado 6.6, and follow-redirects 1.16.2.
# It does not ship npm or msgpack (6.1.1-0's msgpack 1.1.2 was CVE-2026-114613).
# The tag still lags Ubuntu security: apt 3.2.0 (CVE-2026-109518) and pcre2
# 10.46-1build1. upgrade installs apt 3.2.1ubuntu0.1 and pcre2 10.46-1ubuntu0.1.
# /srv/venv has its own pip/setuptools/wheel, so the stale Ubuntu copies can go.
# nosemgrep: semgrep-rules.dockerfile.best-practice.avoid-apt-get-upgrade
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get purge -y python3-pip python3-pip-whl python3-setuptools python3-setuptools-whl python3-wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# oauthlib 4.0.1 is the CVE-2026-49272 fix already in this base. Keep the pin
# so a later base cannot silently install 4.0.0. Do not pin msgpack: JupyterHub
# 6.1.1 does not depend on it, and installing it would put the package back.
# Mako stays pinned at the version this base already ships.
RUN pip install --no-cache-dir --disable-pip-version-check \
        jupyterhub-kubespawner==7.1.0 \
        jupyterhub-idle-culler==2.0.0 \
        oauthenticator==17.4.0 \
        oauthlib==4.0.1 \
        Mako==1.4.3

COPY docker/hub/jupyterhub_config.py \
     docker/hub/notebook_api_spawner.py \
     docker/hub/notebook_names.py \
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
