# ------------------------------------------------------------
# Base image: avaframe
# ------------------------------------------------------------
FROM python:3.12-slim

# ------------------------------------------------------------
# System dependencies (build once, cached)
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    gcc \
    libssl-dev \
    libffi-dev \
    python3-dev \
    libblas-dev \
    liblapack-dev \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Install uv
# ------------------------------------------------------------
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# ------------------------------------------------------------
# Virtual environment
# ------------------------------------------------------------
ENV VENV_DIR=/opt/venv
RUN uv venv --python 3.12 ${VENV_DIR}
ENV VIRTUAL_ENV=${VENV_DIR}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# ------------------------------------------------------------
# Python dependencies (avaframe runtime)
# ------------------------------------------------------------
RUN cat > /tmp/avaframe_requirements.txt <<'REQ'
affine==2.4.0
attrs==24.2.0
certifi==2024.8.30
click==8.1.7
click-plugins==1.1.1
cligj==0.7.2
cython>=3.0
cmcrameri==1.9
configupdater==3.2
contourpy==1.3.0
cycler==0.12.1
deepdiff==8.0.1
deepmerge==2.0
fonttools==4.53.1
kiwisolver==1.4.7
matplotlib==3.9.2
orderly-set==5.2.2
packaging==24.1
pandas==2.2.2
pillow==10.4.0
psutil==6.0.0
pyparsing==3.1.4
pyshp==2.3.1
python-dateutil==2.9.0.post0
pytz==2024.1
rasterio==1.3.11
scipy==1.14.1
seaborn==0.13.2
setuptools
shapely==2.0.6
six==1.16.0
snuggs==1.4.7
tabulate==0.9.0
tzdata==2024.1
wheel
REQ

RUN uv pip install -r /tmp/avaframe_requirements.txt

# ------------------------------------------------------------
# Build & install avaframe
# ------------------------------------------------------------
WORKDIR /build
COPY avaframe/ avaframe/
COPY setup.py pyproject.toml ./

RUN uv run --active python setup.py build_ext --inplace && \
    uv pip install .

# ------------------------------------------------------------
# Metadata
# ------------------------------------------------------------
ARG AVAFRAME_VERSION
LABEL org.opencontainers.image.title="avaframe_bojan"
LABEL org.opencontainers.image.version=${AVAFRAME_VERSION}
