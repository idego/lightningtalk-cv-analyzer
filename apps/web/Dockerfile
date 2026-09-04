FROM node:22-alpine AS base
WORKDIR /app
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV CI=true
RUN corepack enable

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN apk add --no-cache python3 make g++ \
  && pnpm install --frozen-lockfile --config.minimumReleaseAge=0 --config.strictDepBuilds=false \
  && pnpm approve-builds --all \
  && pnpm rebuild better-sqlite3

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN BETTER_AUTH_SECRET="$(head -c 32 /dev/urandom | base64)" ./node_modules/.bin/next build

FROM deps AS feedback-init
COPY --chown=node:node scripts/init-feedback-access.mjs ./scripts/init-feedback-access.mjs
RUN mkdir -p /app/data && chown -R node:node /app/data
USER node
CMD ["node", "scripts/init-feedback-access.mjs"]

FROM base AS runtime
ENV NODE_ENV=production
COPY --chown=node:node --from=build /app/.next/standalone ./
COPY --chown=node:node --from=build /app/.next/static ./.next/static
COPY --chown=node:node --from=build /app/public ./public
COPY --chown=node:node --from=build /app/src/auth.ts ./src/auth.ts
RUN mkdir -p /app/data /pnpm && chown -R node:node /app/data /pnpm
USER node
EXPOSE 3000
CMD ["sh", "-lc", "pnpm --config.minimumReleaseAge=0 dlx @better-auth/cli@1.6.20 migrate --cwd /app --config ./src/auth.ts --yes || true; node server.js"]
