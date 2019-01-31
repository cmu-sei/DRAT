FROM python:3.6-alpine
# Uncomment or build with 'docker build --build-arg http_proxy=......' if behind a proxy
# ARG http_proxy=http://your_proxy_here
# ARG https_proxy=http://your_proxy_here

RUN addgroup -S dbutil && adduser -S -G dbutil dbutil
RUN apk --no-cache add \
    build-base \
    tzdata \
    ca-certificates \
    gcc \
    libffi-dev \
    postgresql-client \
    postgresql-dev

COPY src/requirements.txt src/
RUN pip install --no-cache-dir -r src/requirements.txt

COPY src/db src/db
COPY src/alembic_docker.ini src/alembic.ini
COPY src/migration src/migration

USER dbutil
ENV DOCKER=true

WORKDIR /src
