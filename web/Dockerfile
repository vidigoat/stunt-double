FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
# Optional extra CA (builds behind TLS-intercepting proxies): docker build --secret id=ca,src=/path/ca.crt
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca; fi; npm ci
COPY . .
ARG NEXT_PUBLIC_SITE_URL
ARG API_URL=http://api:8000
# rewrites are resolved at build time in standalone mode, so the API address is a build arg
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL API_URL=$API_URL NEXT_TELEMETRY_DISABLED=1
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca; fi; npm run build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
