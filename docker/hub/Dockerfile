# syntax=docker/dockerfile:1.7
# Pin the Hub tag (not :latest) so pulls stay cacheable and CHP/Node stay in the base.
FROM jupyterhub/jupyterhub:5.5

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
CMD ["jupyterhub", "-f", "/etc/jupyterhub/jupyterhub_config.py"]
