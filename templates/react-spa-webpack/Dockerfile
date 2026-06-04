# syntax=docker/dockerfile:1
#
# Multi-stage build: compile the SPA with Node, then serve the static bundle
# with nginx. The final image contains only nginx + dist/ — no Node, no
# node_modules, no source — so it stays small (~30 MB) and has a minimal
# attack surface.
#
# Node/nginx versions default to the values below but can be overridden so the
# single source of truth in .nvmrc drives the build too:
#   docker build --build-arg NODE_VERSION="$(cat .nvmrc)" -t my-spa .
ARG NODE_VERSION=22
ARG NGINX_VERSION=1.27

# ---- Stage 1: build the SPA ----
FROM node:${NODE_VERSION}-alpine AS build
WORKDIR /app

# Install deps first so this layer caches unless the manifests change.
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Build-time env (e.g. an API key) arrives via a BuildKit secret mounted at
# /run/secrets/env — NOT an ARG or ENV, so it never lands in an image layer or
# the image metadata. webpack's readEnvFile()/DefinePlugin inlines the values.
#   docker build --secret id=env,src=.env -t my-spa .
# Without the secret the build still succeeds (required=false); vars fall back
# to the committed .env defaults.
RUN --mount=type=secret,id=env,required=false \
    sh -c 'set -a; [ -f /run/secrets/env ] && . /run/secrets/env; set +a; npm run build'

# ---- Stage 2: serve the static dist/ with nginx ----
FROM nginx:${NGINX_VERSION}-alpine AS serve
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1
CMD ["nginx", "-g", "daemon off;"]
