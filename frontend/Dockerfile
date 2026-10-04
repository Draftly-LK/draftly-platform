# syntax=docker/dockerfile:1.7
#
# Draftly frontend (Next.js standalone server). Build context is frontend/:
#
#   docker build -t draftly-frontend \
#     --build-arg NEXT_PUBLIC_API_BASE_URL=https://app.example.com \
#     --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_... frontend
#
# NEXT_PUBLIC_* values are inlined by `next build`, so the image is specific to
# one deployment URL and Clerk instance. Server-only secrets (CLERK_SECRET_KEY)
# are supplied at run time, never at build time.

FROM node:22.16.0-slim AS base
ENV PNPM_HOME=/pnpm \
    PATH="/pnpm:$PATH" \
    NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@10.23.0 --activate
# next.config.ts traces from the parent directory, so keep the repo's
# <root>/frontend shape; the standalone server then lands at frontend/server.js.
WORKDIR /repo/frontend


FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile


FROM base AS builder
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_USE_MOCK_PIPELINE=false
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
ARG NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
ARG NEXT_PUBLIC_CLERK_AFTER_SIGN_OUT_URL=/sign-in
ENV NEXT_OUTPUT=standalone \
    NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_USE_MOCK_PIPELINE=$NEXT_PUBLIC_USE_MOCK_PIPELINE \
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY \
    NEXT_PUBLIC_CLERK_SIGN_IN_URL=$NEXT_PUBLIC_CLERK_SIGN_IN_URL \
    NEXT_PUBLIC_CLERK_SIGN_UP_URL=$NEXT_PUBLIC_CLERK_SIGN_UP_URL \
    NEXT_PUBLIC_CLERK_AFTER_SIGN_OUT_URL=$NEXT_PUBLIC_CLERK_AFTER_SIGN_OUT_URL
COPY --from=deps /repo/frontend/node_modules ./node_modules
COPY . .
RUN pnpm build


FROM node:22.16.0-slim AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /app
COPY --from=builder --chown=node:node /repo/frontend/.next/standalone ./
COPY --from=builder --chown=node:node /repo/frontend/.next/static ./frontend/.next/static
COPY --from=builder --chown=node:node /repo/frontend/public ./frontend/public
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/',{redirect:'manual',headers:{Accept:'text/html','Sec-Fetch-Dest':'document'}}).then(r=>process.exit(r.status<400?0:1)).catch(()=>process.exit(1))"]
CMD ["node", "frontend/server.js"]
