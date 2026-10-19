# ==============================================================================
# Betterleaks + Presidio Unified Redaction Service
# Multi-stage build supporting linux/amd64 and linux/arm64
# ==============================================================================

FROM curlimages/curl:8.12.1 AS downloader
ARG BETTERLEAKS_VERSION=v1.8.1
ARG TARGETARCH
WORKDIR /tmp

RUN if [ "$TARGETARCH" = "arm64" ] || [ "$(uname -m)" = "aarch64" ]; then \
        ARCH="linux_arm64"; \
    else \
        ARCH="linux_x64"; \
    fi && \
    curl -sL "https://github.com/betterleaks/betterleaks/releases/download/${BETTERLEAKS_VERSION}/betterleaks_${BETTERLEAKS_VERSION#v}_${ARCH}.tar.gz" -o betterleaks.tar.gz && \
    tar -xzf betterleaks.tar.gz && \
    chmod +x betterleaks

# ------------------------------------------------------------------------------
# Runtime Stage
# ------------------------------------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=downloader /tmp/betterleaks /usr/local/bin/betterleaks
RUN /usr/local/bin/betterleaks version

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download small spaCy models for Presidio NLP PII (English and French)
RUN python -m spacy download en_core_web_sm && \
    python -m spacy download fr_core_news_sm

COPY . .

# Generate gRPC proto stubs
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/ext_mcp.proto

EXPOSE 8080 50052
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/healthz || exit 1

CMD ["python", "main.py"]
