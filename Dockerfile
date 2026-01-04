FROM python:3.13-alpine
COPY --from=astral/uv:0.9.21 /uv /uvx /bin/

WORKDIR /app
# ENV UV_DEFAULT_INDEX https://pypi.tuna.tsinghua.edu.cn/simple
COPY uv.lock pyproject.toml /app/

RUN apk add --update --no-cache  --virtual .build-deps flex bison gcc libc-dev libxml2-dev rust cargo python3-dev libxml2 libxslt-dev && \
    uv sync && \
    apk del .build-deps

RUN apk add openssh git git-lfs && \
    mkdir /root/.ssh

ENV PATH /app/.venv/bin:$PATH