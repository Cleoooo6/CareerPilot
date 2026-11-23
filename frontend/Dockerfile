FROM node:22-alpine AS build

ARG NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm config set registry ${NPM_REGISTRY} \
    && if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080