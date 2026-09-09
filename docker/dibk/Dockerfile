# =================================================================
#
# DIBK image: the official pygeoapi image with our fork's wheel
# swapped in, plus the Starlette stack and our provider/formatter
# packages.
#
# The build context is the repository root, not this directory:
#
#   docker build -f docker/dibk/Dockerfile -t pygeoapi-dibk:0.24.0 .
#
# Context excludes come from Dockerfile.dockerignore next to this
# file, which BuildKit uses in place of the root .dockerignore.
# Building with DOCKER_BUILDKIT=0 falls back to the root one and
# sends a much larger context.
#
# =================================================================

# Keep this in sync with the upstream tag our branch is rebased onto
# (see CLAUDE.md) — the base image supplies every runtime dependency
# of the wheel we build below.
ARG PYGEOAPI_VERSION=0.24.0


# --- stage 1: build our wheel ------------------------------------
#
# Any Python 3 will do: the wheel is pure Python (py3-none-any), so
# it is not tied to the interpreter that builds it. This deliberately
# does not reuse the base image, which has no build toolchain.

FROM python:3.12-slim AS build

WORKDIR /src

COPY . .

RUN pip install --no-cache-dir build \
    && python3 -m build --wheel --outdir /dist


# --- stage 2: the runtime image ----------------------------------

FROM geopython/pygeoapi:${PYGEOAPI_VERSION}

# Needed only to fetch the git+https packages below; purged again in
# the same layer so it does not ship in the final image.
ARG DEB_BUILD_DEPS="\
    git"

# starlette/uvicorn: the base image ships the Flask stack only, and we
# run under Starlette.
# The two git packages are our own, and are installed with their
# dependencies (unlike the wheel below).
ARG PYTHON_PACKAGES="\
    starlette \
    uvicorn \
    git+https://github.com/Arkitektum/pygeoapi.providers.git@main \
    git+https://github.com/Arkitektum/pygeoapi.formatter.gml-npad.git@develop"

COPY --from=build /dist/*.whl /tmp/

# Replacing upstream's pygeoapi takes three steps: drop the installed
# distribution, delete /pygeoapi/pygeoapi (the base image adds the
# source tree to the path as well, and it would shadow our package),
# then install our wheel. --no-deps keeps pip from touching the
# dependency set the base image already pinned.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ${DEB_BUILD_DEPS} \
    && /venv/bin/python3 -m pip uninstall -y pygeoapi \
    && rm -rf /pygeoapi/pygeoapi \
    && /venv/bin/python3 -m pip install --no-cache-dir --no-deps --force-reinstall /tmp/*.whl \
    && /venv/bin/python3 -m pip install --no-cache-dir ${PYTHON_PACKAGES} \
    && rm -f /tmp/*.whl \
    && apt-get remove --purge -y ${DEB_BUILD_DEPS} \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Fail the build rather than the container if the swap did not take.
RUN /venv/bin/python3 -c "import pygeoapi, sys; \
    sys.exit(0 if '+dibk' in pygeoapi.__version__ else \
    'unexpected pygeoapi version: ' + pygeoapi.__version__)"
