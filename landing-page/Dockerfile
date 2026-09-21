FROM node:22.16.0-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production PORT=8080 HOST=0.0.0.0
RUN groupadd --system --gid 1001 draftly && useradd --system --uid 1001 --gid draftly draftly
COPY --chown=draftly:draftly pilot-api.mjs serve.mjs ./
COPY --chown=draftly:draftly site-mirror ./site-mirror
USER draftly
EXPOSE 8080
CMD ["node", "serve.mjs"]
