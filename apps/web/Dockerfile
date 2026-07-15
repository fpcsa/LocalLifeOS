FROM node:22-alpine

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /workspace

COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/shared-types/package.json ./packages/shared-types/package.json
COPY packages/ui/package.json ./packages/ui/package.json
RUN npm ci

COPY apps/web/ ./apps/web/
COPY packages/shared-types/ ./packages/shared-types/
COPY packages/ui/ ./packages/ui/

WORKDIR /workspace/apps/web

EXPOSE 3000

CMD ["npm", "run", "dev:container"]
