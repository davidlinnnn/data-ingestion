# THROWAWAY. Linux execution image; build context is the parent prototype folder.
ARG BASE_IMAGE=python:3.12.13-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.8.22
WORKDIR /experiment
COPY pyproject.toml uv.lock ./
COPY k8s/linux-requirements.txt k8s/linux-requirements.txt
RUN uv venv .venv --python /usr/local/bin/python3 && uv pip install --python .venv/bin/python --no-deps -r k8s/linux-requirements.txt
RUN uv pip install --python .venv/bin/python --no-deps --index-url https://download.pytorch.org/whl/cpu torch==2.14.0+cpu torchvision==0.29.0+cpu
COPY temporal-requirements.txt ./
RUN uv pip install --python .venv/bin/python -r temporal-requirements.txt boto3==1.40.24
COPY *.py ocr-reference.json ./
COPY evidence/native-method.json evidence/native-method.json
COPY fixtures/ fixtures/
COPY PROTOTYPE-wipe-me/hf/ PROTOTYPE-wipe-me/hf/
COPY k8s/ k8s/
ENV HF_HUB_OFFLINE=1 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
ENTRYPOINT ["/experiment/.venv/bin/python"]
CMD ["k8s/worker.py"]
