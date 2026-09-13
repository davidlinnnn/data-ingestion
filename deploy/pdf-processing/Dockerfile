# Base is the pinned, qualified Linux Docling runtime; provide its immutable digest.
ARG DOCLING_RUNTIME
FROM ${DOCLING_RUNTIME}
COPY src/pdf_processing /app/pdf_processing
COPY deploy/pdf-processing/worker.py /app/worker.py
COPY deploy/pdf-processing/profiles /app/profiles
ENV PYTHONPATH=/app
ENTRYPOINT ["/experiment/.venv/bin/python", "/app/worker.py"]
