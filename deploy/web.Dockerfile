# Next.js frontend. /api/* is proxied to the private api container.
FROM node:20-bookworm-slim AS build
WORKDIR /web
ARG NEXT_PUBLIC_SITE_URL
ARG API_PROXY_TARGET=http://api:8000
ENV NEXT_PUBLIC_SITE_URL=${NEXT_PUBLIC_SITE_URL} \
    API_PROXY_TARGET=${API_PROXY_TARGET} \
    NEXT_PUBLIC_STATIC_DATA=0 \
    NEXT_TELEMETRY_DISABLED=1
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM node:20-bookworm-slim
WORKDIR /web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000
COPY --from=build /web ./
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000", "-H", "0.0.0.0"]
