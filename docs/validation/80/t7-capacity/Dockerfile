# The measurement image of #136: kp-canonicalization on linux/arm64, for the inference worker under
# the 4 CPU / 5 GiB limits of #93 §4. Not the release image (#78, #135). Build from the repo root:
#   docker build --platform linux/arm64 -f docs/validation/80/t7-capacity/Dockerfile -t kp-canonicalization:t7 .
# Model weights are mounted read-only at /models; nothing is downloaded at run time.
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /bin/uv
# opencv-python (from rapidocr) links against X and GL even when nothing is displayed.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxcb1 \
    && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY tests/profiles ./tests/profiles
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
ENV PATH=/app/.venv/bin:$PATH HF_HUB_OFFLINE=1 DOCLING_ARTIFACTS_PATH=/models
ENTRYPOINT ["kp-canonicalization"]
