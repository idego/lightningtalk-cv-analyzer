FROM node:22-alpine AS base
WORKDIR /app
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV CI=true
RUN corepack enable

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN apk add --no-cache python3 make g++ \
  && pnpm install --frozen-lockfile --config.minimumReleaseAge=0 --config.strictDepBuilds=false \
  && pnpm approve-builds --all \
  && pnpm rebuild better-sqlite3

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN ./node_modules/.bin/next build

FROM base AS runtime
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
COPY --from=build /app/src/auth.ts ./src/auth.ts
EXPOSE 3000
CMD ["sh", "-lc", "pnpm --config.minimumReleaseAge=0 dlx @better-auth/cli@latest migrate --cwd /app --config ./src/auth.ts --yes || true; node server.js"]
