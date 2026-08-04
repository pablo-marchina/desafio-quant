# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    HF_HOME=/opt/model-cache \
    SENTENCE_TRANSFORMERS_HOME=/opt/model-cache

ARG TORCH_VERSION=2.12.1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY config ./config
COPY migrations ./migrations
COPY alembic.ini ./
# .dockerignore removes databases, exports, raw/staging data, and other runtime artifacts.
COPY data ./data
COPY models/ai_native_classifier ./models/ai_native_classifier

# The backend runs inference on CPU. Installing the official CPU-only PyTorch
# wheel before the project prevents pip from pulling multi-gigabyte CUDA wheels
# such as nvidia-cusolver into this slim runtime image. The cache mount survives
# failed builds without being copied into the final image.
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install -e ".[full,observability]"

RUN mkdir -p /app/data/product /opt/model-cache \
    && chown -R nobody:nogroup /app/data /opt/model-cache

USER nobody

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
