# Draftly landing page: the saved site plus the pilot-request intake route.
# serve.mjs, pilot-api.mjs and cache-policy.mjs use only Node built-ins, so
# there is nothing to install.
#
#   docker build -t draftly-landing landing-page
FROM node:22.16.0-alpine
ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=4173 \
    TRUST_PROXY=1 \
    PILOT_REQUESTS_DIR=/data/pilot-requests
WORKDIR /app
COPY --chown=node:node serve.mjs pilot-api.mjs cache-policy.mjs ./
COPY --chown=node:node site-mirror ./site-mirror
# The intake directory holds email addresses: private, writable, never under /app.
RUN mkdir -p /data/pilot-requests && chown -R node:node /data
USER node
EXPOSE 4173
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:4173/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["node", "serve.mjs"]
