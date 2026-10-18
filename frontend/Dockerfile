# syntax=docker/dockerfile:1

FROM node:24-alpine AS build
WORKDIR /app
# Dependencies get their own layer, rebuilt only when the lock file changes.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY . .
RUN npm run build


# The unprivileged variant listens on 8080 and runs as a non-root user out of the box.
FROM nginxinc/nginx-unprivileged:1.30-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
