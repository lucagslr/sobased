# dev: Vite dev server behind Caddy. build: static bundle for production.
FROM node:22-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
CMD ["npm", "run", "dev"]

FROM dev AS build
RUN npm run build
