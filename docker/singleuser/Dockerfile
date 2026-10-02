# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /opt/mip-build

# Third-party deps first: only uv.lock / pyproject changes rebuild this layer.
# uv venvs have no pip; add it so notebook `%pip install` works.
COPY pyproject.toml uv.lock ./
COPY python-client/pyproject.toml ./python-client/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --no-install-package mip \
    && uv pip install --python /opt/venv/bin/python pip==26.2.1

# Our packages: seconds to rebuild. uv.sources marks mip editable for local dev;
# --no-editable copies it into the venv. --inexact keeps pip.
COPY python-client/README.md ./python-client/
COPY python-client/mip ./python-client/mip
COPY mip_jupyter_dev ./mip_jupyter_dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --inexact

# codex-acp's npm package is a node shim around a native binary; ship the binary only.
# One stage per arch: an unsupported TARGETARCH fails the build (no such stage).
# Checksums are the npm tarballs' (verified against the registry's dist.integrity).
FROM scratch AS codex-acp-amd64
ADD --checksum=sha256:9acfd7576986dc571a35479cbbf72790df40c90b9b89b436bc82500372918ee8 \
    https://registry.npmjs.org/@zed-industries/codex-acp-linux-x64/-/codex-acp-linux-x64-0.16.0.tgz /acp.tgz

FROM scratch AS codex-acp-arm64
ADD --checksum=sha256:70f6126de278bb854f7df50cbd748b58fd01a34a5e58f16976990064bb1c59a1 \
    https://registry.npmjs.org/@zed-industries/codex-acp-linux-arm64/-/codex-acp-linux-arm64-0.16.0.tgz /acp.tgz

FROM codex-acp-${TARGETARCH} AS codex-acp-tgz

FROM python:3.12-slim-bookworm AS codex-acp
RUN --mount=from=codex-acp-tgz,source=/acp.tgz,target=/tmp/acp.tgz \
    tar -xzf /tmp/acp.tgz -C /tmp package/bin/codex-acp \
    && install -m 755 /tmp/package/bin/codex-acp /usr/local/bin/codex-acp

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PLATFORM_BACKEND_URL=http://platform-backend:8080/services \
    JUPYTER_HOST=0.0.0.0 \
    JUPYTER_PORT=8888 \
    MIP_WORK_DIR=/home/jovyan/work \
    MIP_WORKSPACE_TEMPLATE=/opt/mip-workspace-template \
    MIP_JUPYTER_ROOT=/home/jovyan/work \
    MIP_AGENT_DOCS=/opt/mip-agent-docs \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

# gid 100 (users) matches KubeSpawner fsGroup.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -g 100 -s /bin/bash jovyan \
    && mkdir -p /home/jovyan/work /etc/profile.d \
    && printf '%s\n' 'export PATH="/opt/venv/bin:$PATH"' > /etc/profile.d/mip-venv.sh \
    && chown -R 1000:100 /home/jovyan

COPY --from=codex-acp /usr/local/bin/codex-acp /usr/local/bin/codex-acp
COPY --from=build --chown=1000:100 /opt/venv /opt/venv

COPY --chown=1000:100 workspace/ "${MIP_WORKSPACE_TEMPLATE}/"
COPY --chown=1000:100 docs/user/ "${MIP_WORKSPACE_TEMPLATE}/docs/"
COPY --chown=1000:100 docs/llm/ /opt/mip-agent-docs/llm/
COPY --chown=1000:100 AGENTS.md /opt/mip-agent-docs/
COPY --chmod=755 docker/singleuser/entrypoint.sh /usr/local/bin/mip-jupyter-entrypoint.sh

WORKDIR /home/jovyan/work
USER jovyan

EXPOSE 8888
ENTRYPOINT ["tini", "--", "mip-jupyter-entrypoint.sh"]
