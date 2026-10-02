# syntax=docker/dockerfile:1.7
# Pin the Hub tag (not :latest) so pulls stay cacheable and CHP/Node stay in the base.
FROM jupyterhub/jupyterhub:5.5

# Base tag lags on OS security fixes (e.g. openssl). /srv/venv has its own
# pip/setuptools, so the stale Ubuntu copies can go.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get purge -y python3-pip python3-pip-whl python3-setuptools python3-setuptools-whl \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --disable-pip-version-check \
        jupyterhub-kubespawner==7.1.0 \
        oauthenticator

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
