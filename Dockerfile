# A Linux environment with Node.js, Python, MiniMax, KUMA and OTel.
FROM node:24-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv git \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    MCODE_BIN="/opt/minimax/node_modules/@minimax-ai/code/cli.js" \
    PYTHONUNBUFFERED=1 \
    KUMA_DISABLE_UPDATE_CHECK=1

RUN pip install --no-cache-dir \
        "kuma-defuzex[otel]==0.3.8" \
        "minimax-code-sdk==0.1.0" \
        "opentelemetry-sdk==1.38.0" \
    && npm install --prefix /opt/minimax \
        @minimax-ai/code@0.7.4 --registry=https://registry.npmjs.org/

WORKDIR /workspace
CMD ["bash"]
