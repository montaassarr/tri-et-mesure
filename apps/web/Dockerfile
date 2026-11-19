# Build context: repository root (docker build -f apps/web/Dockerfile .)
# Debian (glibc), not Alpine: rollup's native parser overflows musl's small thread stack
# ("Code is nested too deeply").
FROM --platform=$BUILDPLATFORM node:22-slim AS builder
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile --filter web
COPY apps/web/ apps/web/
RUN pnpm --filter web build

FROM nginx:1.27-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /repo/apps/web/dist /usr/share/nginx/html
EXPOSE 8080
