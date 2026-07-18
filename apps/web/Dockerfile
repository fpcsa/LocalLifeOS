FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2

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

RUN npm run build --workspace @locallife/web

RUN chown -R node:node /workspace/apps/web

USER node

WORKDIR /workspace/apps/web

EXPOSE 3000

CMD ["npm", "run", "start:container"]
