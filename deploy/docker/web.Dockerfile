# Built frontend served by nginx, which also forwards /api to the API container.
FROM node:24.14.0-bookworm-slim AS build
WORKDIR /app/frontend
COPY .node-version /app/.node-version
COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/scripts scripts
RUN npm ci
COPY frontend ./
RUN npm run build

FROM nginx:1.27.5-alpine
COPY deploy/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
