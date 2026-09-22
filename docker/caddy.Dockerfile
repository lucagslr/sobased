# Production edge: the Vue bundle baked into the Caddy image. Build context is
# the repository root (docker-compose.prod.yml).
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv/www
COPY Caddyfile.prod /etc/caddy/Caddyfile
