# Multi-stage build:
# 1. node:20-alpine compiles the React app via `vite build` → /app/dist
# 2. nginx:1.27-alpine serves the dist files and proxies /api + /media
#    to the nms10-backend container on the same docker network.
#
# That means the frontend and the API live at the SAME origin from the
# browser's perspective, so no CORS headache, no /api URL config — just
# nms10.online for everything.

FROM node:20-alpine AS build
WORKDIR /app

# Install deps first (cached layer) before copying source
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ----- runtime -----
FROM nginx:1.27-alpine

# Drop the default nginx config; ours handles SPA fallback + API proxy
RUN rm /etc/nginx/conf.d/default.conf
COPY docker/frontend.nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# Nginx doesn't have a built-in healthcheck, so we use wget against itself.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q -O- http://localhost/ >/dev/null || exit 1
