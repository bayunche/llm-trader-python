# 生产部署镜像
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=off \
    PIP_DEFAULT_TIMEOUT=120 \
    PROJECT_ROOT=/app \
    PYTHONPATH=/app/src

WORKDIR ${PROJECT_ROOT}

COPY requirements.dev.txt /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && apt-get purge -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . ${PROJECT_ROOT}

RUN chmod +x docker/entrypoint.sh

ENTRYPOINT ["bash", "docker/entrypoint.sh"]
