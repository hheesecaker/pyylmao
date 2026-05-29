FROM python:3.12-slim

ARG TARGETARCH
ARG CLOUDFLARED_VERSION=2026.5.2

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYYLMAO_STATE=/var/lib/pyylmao/pyylmao-state.json \
    PYYLMAO_WWW_DIR=/var/lib/pyylmao/www \
    PYYLMAO_WWW_BASE_URL_FILE=/var/lib/pyylmao/www-base-url

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
        amd64) cloudflared_arch=amd64 ;; \
        arm64) cloudflared_arch=arm64 ;; \
        *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL \
        "https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-linux-${cloudflared_arch}" \
        -o /usr/local/bin/cloudflared; \
    chmod +x /usr/local/bin/cloudflared

WORKDIR /app
COPY pyproject.toml README.md ./
COPY irc ./irc
COPY irclib ./irclib
COPY llm ./llm
COPY pyylmao ./pyylmao
COPY tests ./tests
COPY docs ./docs

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN chmod -R a+rX /app

RUN useradd --create-home --uid 10001 pyylmao \
    && mkdir -p /var/lib/pyylmao/www \
    && chown -R pyylmao:pyylmao /var/lib/pyylmao

USER pyylmao

CMD ["python", "-m", "pyylmao"]
