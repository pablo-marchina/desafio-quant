# syntax=docker/dockerfile:1.7
FROM nvcr.io/nvidia/tritonserver:26.06-py3

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    HF_HOME=/opt/triton-model-cache \
    SENTENCE_TRANSFORMERS_HOME=/opt/triton-model-cache \
    CE_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2

ARG TORCH_VERSION=2.12.1

# The Triton base image provides a Debian-managed pip installation. Do not try
# to replace it with `pip install --upgrade pip`, because the Debian package has
# no wheel RECORD file and cannot be uninstalled by pip.
#
# The model repository declares KIND_CPU, so install the official CPU-only
# PyTorch wheel. This avoids downloading duplicate CUDA runtime wheels inside an
# already CUDA-enabled Triton image. BuildKit keeps downloads across retries.
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu \
    && python3 -m pip install "sentence-transformers>=3.4,<4" \
    && python3 -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device='cpu')"

RUN mkdir -p /models /opt/triton-model-cache

HEALTHCHECK --interval=20s --timeout=8s --start-period=90s --retries=10 \
  CMD curl -fsS http://127.0.0.1:8000/v2/models/cross_encoder/ready || exit 1

CMD ["tritonserver", "--model-repository=/models", "--model-control-mode=explicit", "--load-model=cross_encoder", "--strict-readiness=true"]
