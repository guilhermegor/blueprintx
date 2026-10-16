# syntax=docker/dockerfile:1
ARG NODE_VERSION=22
ARG NGINX_VERSION=1.27

FROM node:${NODE_VERSION}-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

RUN --mount=type=secret,id=env,required=false \
    sh -c 'set -a; [ -f /run/secrets/env ] && . /run/secrets/env; set +a; npm run build'

FROM nginx:${NGINX_VERSION}-alpine AS serve
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1
CMD ["nginx", "-g", "daemon off;"]
